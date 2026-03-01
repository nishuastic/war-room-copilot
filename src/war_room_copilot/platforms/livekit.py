"""LiveKit platform implementation."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

from livekit import agents, api
from livekit.agents import (
    Agent,
    AgentSession,
    RunContext,
    function_tool,
)
from livekit.plugins import silero, speechmatics  # noqa: F401
from livekit.plugins.speechmatics import SpeakerIdentifier, TurnDetectionMode
from speechmatics.voice._models import AdditionalVocabEntry

from war_room_copilot.config import get_settings
from war_room_copilot.graph.incident_graph import incident_graph
from war_room_copilot.graph.nodes.github_research import close_mcp_client
from war_room_copilot.llm import create_llm
from war_room_copilot.platforms.base import (
    SpeakerInfo,
    load_agent_prompt,
    load_known_speakers,
    save_speakers,
)
from war_room_copilot.tts import create_tts

logger = logging.getLogger("war-room-copilot.platforms.livekit")

# Rooms with no participants older than this are purged on worker startup.
_STALE_ROOM_AGE_SECONDS = 120

# Direct-address mode resets after this many seconds of no wake word.
_DIRECT_ADDRESS_TIMEOUT_S = 60.0

# Pattern for wake word detection.  Matches "hey copilot", "hey, copilot",
# "hey co-pilot", "hey co pilot", etc.  Case-insensitive.
_WAKE_WORD_RE = re.compile(
    r"\bhey[,.]?\s+co[-\s]?pilot\b",
    re.IGNORECASE,
)

# Backchannel phrases for natural conversation UX.
_BACKCHANNEL_PHRASES = [
    "mm-hmm",
    "understood",
    "got it",
    "right",
    "I see",
    "okay",
]

# Maximum accumulated items before oldest entries are trimmed.
_MAX_TRANSCRIPT = 500
_MAX_FINDINGS = 100
_MAX_DECISIONS = 100

# SRE/incident vocabulary for Speechmatics custom dictionary.
# Improves recognition of domain-specific terms that general STT misrecognizes.
INCIDENT_VOCAB = [
    AdditionalVocabEntry(content="Kubernetes"),
    AdditionalVocabEntry(content="kubectl", sounds_like=["kube-control", "kube-cuddle"]),
    AdditionalVocabEntry(content="MTTR", sounds_like=["M T T R", "mean time to recovery"]),
    AdditionalVocabEntry(content="MTTD", sounds_like=["M T T D", "mean time to detect"]),
    AdditionalVocabEntry(content="PagerDuty"),
    AdditionalVocabEntry(content="Datadog"),
    AdditionalVocabEntry(content="Speechmatics"),
    AdditionalVocabEntry(content="LangGraph"),
    AdditionalVocabEntry(content="LiveKit"),
    AdditionalVocabEntry(content="OpenTelemetry", sounds_like=["open telemetry"]),
    AdditionalVocabEntry(content="Prometheus"),
    AdditionalVocabEntry(content="Grafana"),
    AdditionalVocabEntry(content="SLO", sounds_like=["S L O", "service level objective"]),
    AdditionalVocabEntry(content="SLA", sounds_like=["S L A", "service level agreement"]),
    AdditionalVocabEntry(content="RCA", sounds_like=["R C A", "root cause analysis"]),
    AdditionalVocabEntry(content="postmortem"),
    AdditionalVocabEntry(content="runbook"),
    AdditionalVocabEntry(content="rollback"),
    AdditionalVocabEntry(content="hotfix"),
    AdditionalVocabEntry(content="canary deployment"),
    AdditionalVocabEntry(content="war room"),
    AdditionalVocabEntry(content="p zero", sounds_like=["P0", "priority zero"]),
    AdditionalVocabEntry(content="p one", sounds_like=["P1", "priority one"]),
    AdditionalVocabEntry(
        content="hey copilot",
        sounds_like=["hey co-pilot", "hey co pilot"],
    ),
]


def _trim_list(lst: list[Any], max_len: int) -> list[Any]:
    """Trim a list to the last ``max_len`` items if it exceeds the limit."""
    if len(lst) > max_len:
        return lst[-max_len:]
    return lst


def _to_livekit_speakers(speakers: list[SpeakerInfo]) -> list[SpeakerIdentifier]:
    """Convert platform-agnostic SpeakerInfo to LiveKit's SpeakerIdentifier."""
    return [
        SpeakerIdentifier(label=s.label, speaker_identifiers=s.speaker_identifiers)
        for s in speakers
    ]


class WarRoomAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=load_agent_prompt(),
            tools=[reason_tool],
        )


# Session state is stored here and set by _entrypoint before session.start().
# The reason_tool closure captures this reference.
_session_state: dict[str, Any] = {}
_state_lock: asyncio.Lock | None = None


async def _invoke_graph(query: str) -> str:
    """Run the incident graph with the current session state.

    Uses ``astream()`` to get per-node updates, logging each step and
    emitting trace events to the dashboard.  State is accumulated across
    calls so the graph has memory.
    """
    assert _state_lock is not None, "_entrypoint must initialize _state_lock"

    async with _state_lock:
        input_state = {
            **_session_state,
            "query": query,
        }

    # Stream through the graph node-by-node for observability
    result: dict[str, Any] = {}
    async for chunk in incident_graph.astream(input_state):
        # Each chunk is a dict keyed by node name with that node's output
        for node_name, node_output in chunk.items():
            if node_name == "__end__":
                continue
            logger.info("[Graph] %s completed", node_name)
            # Emit trace event to dashboard via session state
            trace_entry = {
                "node": node_name,
                "query": query,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            }
            async with _state_lock:
                traces = _session_state.setdefault("graph_traces", [])
                traces.append(trace_entry)
            # Merge node output into result (last write wins per key)
            if isinstance(node_output, dict):
                for k, v in node_output.items():
                    if k in ("findings", "decisions", "transcript") and isinstance(v, list):
                        result.setdefault(k, []).extend(v)
                    else:
                        result[k] = v

    # Persist accumulated state for next invocation (with trimming)
    async with _state_lock:
        _session_state["findings"] = _trim_list(
            result.get("findings", _session_state.get("findings", [])),
            _MAX_FINDINGS,
        )
        _session_state["decisions"] = _trim_list(
            result.get("decisions", _session_state.get("decisions", [])),
            _MAX_DECISIONS,
        )
        _session_state["messages"] = result.get("messages", _session_state.get("messages", []))

    # Extract the last AI message as the response text
    messages = result.get("messages", [])
    if messages:
        last = messages[-1]
        content = getattr(last, "content", str(last))
        if isinstance(content, str):
            return content
    return "I processed your request but have no additional information."


@function_tool(
    name="reason",
    description=(
        "Invoke the reasoning graph for deep investigation, summarization, "
        "recall of past decisions, or any request that needs GitHub search, "
        "incident context, or multi-step reasoning. Use this whenever the user "
        "asks you to investigate, search code, find issues, summarize the incident, "
        "recall what was discussed, or generate a post-mortem."
    ),
)
async def reason_tool(ctx: RunContext, query: str) -> str:  # type: ignore[type-arg]
    """Run the reasoning graph to investigate, summarize, or recall.

    Args:
        query: The user's request or question to reason about.
    """
    import sys

    print(f"[REASON_TOOL] invoked with query: {query}", file=sys.stderr, flush=True)
    logger.info("reason_tool invoked: %s", query)
    try:
        result = await _invoke_graph(query)
        print(
            f"[REASON_TOOL] result: {result[:200] if result else 'empty'}",
            file=sys.stderr,
            flush=True,
        )
        logger.info("reason_tool result: %s", result[:200] if result else "empty")
        return result
    except Exception as exc:
        from war_room_copilot.graph.llm import classify_llm_error
        from war_room_copilot.tools.github_mcp import (
            LLMError,
            WarRoomToolError,
        )

        if isinstance(exc, WarRoomToolError):
            err_detail = f"{type(exc).__name__}: {exc}"
        elif isinstance(exc, LLMError):
            err_detail = f"{type(exc).__name__}: {exc}"
        else:
            llm_err = classify_llm_error(exc)
            err_detail = f"{type(llm_err).__name__}: {llm_err}"
        print(
            f"[REASON_TOOL] FAILED ({err_detail})",
            file=sys.stderr,
            flush=True,
        )
        logger.error("reason_tool failed (%s)", err_detail)
        return f"Sorry, I encountered an error: {err_detail}"


def _prewarm(proc: agents.JobProcess) -> None:
    """Prewarm callback: pre-import LLM plugins and clean up stale rooms.

    Runs once when each worker process initializes — before any job is
    accepted.  Two responsibilities:

    1. **Plugin registration** — LiveKit plugins must be imported on the
       main thread (``Plugin.register_plugin`` enforces this).  The
       ``create_llm()`` factory lazy-imports plugins, so if the first
       call happens in the entrypoint (which runs on a worker thread in
       THREAD mode, or the child's main thread in PROCESS mode) the
       import can fail.  Pre-importing here guarantees registration
       happens on each process's main thread.

    2. **Stale room cleanup** — deletes empty rooms left over from
       previous sessions so they don't block new dispatch.
    """
    import os
    import sys
    import threading
    import traceback

    pid = os.getpid()
    tid = threading.current_thread().name
    diag = f"[PREWARM] pid={pid} thread={tid}\n"

    # Pre-import LLM and TTS plugins so they register on the main thread.
    from war_room_copilot.llm import create_llm
    from war_room_copilot.tts import create_tts

    try:
        create_llm()
        diag += "[PREWARM] LLM plugin registered OK\n"
    except Exception:
        diag += f"[PREWARM] LLM pre-import failed:\n{traceback.format_exc()}\n"
        logger.debug("LLM pre-import (expected if API key missing)", exc_info=True)

    try:
        create_tts()
        diag += "[PREWARM] TTS plugin registered OK\n"
    except Exception:
        diag += f"[PREWARM] TTS pre-import failed:\n{traceback.format_exc()}\n"
        logger.debug("TTS pre-import (expected if API key missing)", exc_info=True)

    # Write diagnostics to file — child process stdout may be invisible to Docker
    try:
        with open(f"/app/data/prewarm_{pid}.log", "w") as f:
            f.write(diag)
    except OSError:
        pass

    # Also print to stderr (more likely to appear in Docker logs)
    print(diag, file=sys.stderr, flush=True)

    asyncio.run(_purge_stale_rooms_async())


async def _purge_stale_rooms_async() -> None:
    """Async implementation of stale room cleanup."""
    cfg = get_settings()
    lk_api = api.LiveKitAPI(
        url=cfg.livekit_url.replace("ws://", "http://").replace("wss://", "https://"),
        api_key=cfg.livekit_api_key,
        api_secret=cfg.livekit_api_secret,
    )
    try:
        rooms_resp = await lk_api.room.list_rooms(api.ListRoomsRequest())
        now_s = int(time.time())
        for room in rooms_resp.rooms:
            age_s = now_s - room.creation_time
            if room.num_participants == 0 and age_s > _STALE_ROOM_AGE_SECONDS:
                logger.info(
                    "Purging stale room %s (age=%ds, participants=%d)",
                    room.name,
                    age_s,
                    room.num_participants,
                )
                await lk_api.room.delete_room(api.DeleteRoomRequest(room=room.name))
        logger.info("Startup cleanup: checked %d rooms", len(rooms_resp.rooms))
    except Exception:
        logger.warning("Stale room cleanup failed — continuing anyway", exc_info=True)
    finally:
        await lk_api.aclose()


async def _entrypoint(ctx: agents.JobContext) -> None:
    """LiveKit agent entrypoint — joins room, wires audio pipeline, runs."""
    import os
    import sys

    pid = os.getpid()
    print(f"[ENTRYPOINT] pid={pid} room={ctx.room.name}", file=sys.stderr, flush=True)
    try:
        await _entrypoint_inner(ctx)
    except Exception:
        import traceback

        crash_msg = f"[ENTRYPOINT CRASH] pid={pid}\n{traceback.format_exc()}"
        print(crash_msg, file=sys.stderr, flush=True)
        with open(f"/app/data/entrypoint_crash_{pid}.log", "w") as _f:
            _f.write(crash_msg)
        raise


async def _entrypoint_inner(ctx: agents.JobContext) -> None:
    """Inner entrypoint — actual implementation."""
    global _session_state, _state_lock  # noqa: PLW0603

    await ctx.connect()
    logger.info("Room: %s", ctx.room.name)

    # Fresh session state per room — prevents cross-session bleed
    _session_state = {
        "transcript": [],
        "transcript_structured": [],
        "findings": [],
        "decisions": [],
        "speakers": {},
        "messages": [],
        "direct_address": False,
        "direct_address_until": 0.0,
    }
    _state_lock = asyncio.Lock()

    # Block until the room disconnects — without this, the entrypoint returns
    # immediately and LiveKit considers the job done (agent leaves after ~120ms).
    disconnect_event = asyncio.Event()
    ctx.room.on("disconnected", lambda _reason: disconnect_event.set())

    # Register shutdown callback so resources are cleaned up when the job ends.
    async def _on_shutdown() -> None:
        logger.info("Job shutting down for room %s — cleaning up", ctx.room.name)
        disconnect_event.set()
        await close_mcp_client()
        # Cancel background tasks (they hold references to session/stt)
        for task in list(_background_tasks):
            task.cancel()
        _session_state.clear()
        logger.info("Shutdown complete for room %s", ctx.room.name)

    ctx.add_shutdown_callback(_on_shutdown)

    # Set to track background tasks and prevent GC
    _background_tasks: set[asyncio.Task[Any]] = set()

    def _launch_task(coro: Any, *, name: str) -> asyncio.Task[Any]:
        """Create a background task with proper lifecycle management."""
        task = asyncio.create_task(coro, name=name)
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return task

    known_speakers = load_known_speakers()
    lk_speakers = _to_livekit_speakers(known_speakers)

    # Seed session state with known speakers
    for s in known_speakers:
        _session_state["speakers"][s.label] = s.label

    cfg = get_settings()
    stt = speechmatics.STT(
        operating_point=cfg.speechmatics_operating_point,
        turn_detection_mode=TurnDetectionMode.SMART_TURN,
        enable_diarization=True,
        max_speakers=cfg.speechmatics_max_speakers,
        speaker_sensitivity=cfg.speechmatics_speaker_sensitivity,
        additional_vocab=INCIDENT_VOCAB,
        enable_entities=cfg.speechmatics_enable_entities,
        speaker_active_format="<{speaker_id}>{text}</{speaker_id}>",
        speaker_passive_format=("<PASSIVE><{speaker_id}>{text}</{speaker_id}></PASSIVE>"),
        focus_speakers=["S1"],
        known_speakers=lk_speakers,
    )

    session = AgentSession(  # type: ignore[var-annotated]
        stt=stt,
        llm=create_llm(),
        tts=create_tts(),
        vad=silero.VAD.load(),
    )

    await session.start(
        room=ctx.room,
        agent=WarRoomAgent(),
    )

    # --- Feed STT transcript into session state ---
    @session.on("user_input_transcribed")
    def _on_transcript(event: Any) -> None:
        if not getattr(event, "is_final", False):
            return
        text = getattr(event, "transcript", "").strip()
        if not text:
            return
        speaker = getattr(event, "speaker_id", None) or "Unknown"
        display_name = _session_state["speakers"].get(speaker, speaker)
        ts = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")
        line = f"[{ts}] {display_name}: {text}"
        _session_state["transcript"].append(line)
        # Trim transcript to prevent unbounded growth
        if len(_session_state["transcript"]) > _MAX_TRANSCRIPT:
            _session_state["transcript"] = _session_state["transcript"][-_MAX_TRANSCRIPT:]
        # Structured entry for timeline generation
        _session_state["transcript_structured"].append(
            {
                "speaker": display_name,
                "text": text,
                "timestamp": ts,
                "epoch": time.time(),
            }
        )
        if len(_session_state["transcript_structured"]) > _MAX_TRANSCRIPT:
            _session_state["transcript_structured"] = _session_state["transcript_structured"][
                -_MAX_TRANSCRIPT:
            ]
        logger.debug("Transcript: %s", line)

        # --- Wake word detection ---
        if _WAKE_WORD_RE.search(text):
            _session_state["direct_address"] = True
            _session_state["direct_address_until"] = (
                time.time() + _DIRECT_ADDRESS_TIMEOUT_S
            )
            logger.info(
                "Wake word detected from %s — direct address mode ON",
                display_name,
            )
            _launch_task(
                session.generate_reply(
                    instructions=(
                        f"{display_name} said 'hey copilot'. "
                        "Acknowledge briefly that you are listening "
                        "and ready to help."
                    )
                ),
                name="wake_word_ack",
            )
        elif (
            _session_state["direct_address"]
            and time.time() > _session_state["direct_address_until"]
        ):
            _session_state["direct_address"] = False
            logger.info("Direct address mode timed out — OFF")

    if known_speakers:
        names = ", ".join(s.label for s in known_speakers)
        await session.generate_reply(
            instructions=(
                f"Greet the team. You recognize: {names}. Welcome them back by name. Be brief."
            )
        )
    else:
        await session.generate_reply(
            instructions=(
                "Greet the team briefly. Say you are War Room Copilot and ready to listen."
            )
        )

    async def capture_voiceprints() -> None:
        await asyncio.sleep(15)
        while True:
            try:
                result = await stt.get_speaker_ids()
                if result:
                    save_speakers(result)
            except Exception as exc:
                logger.error(
                    "Voiceprint capture failed (%s): %s",
                    type(exc).__name__,
                    exc,
                )
            await asyncio.sleep(30)

    # --- Background contradiction monitoring ---
    async def monitor_contradictions() -> None:
        """Periodically check transcript for contradictions."""
        from war_room_copilot.graph.nodes.contradict import (
            run_contradiction_check,
        )

        await asyncio.sleep(30)  # wait for transcript to accumulate
        while True:
            async with _state_lock:
                transcript = list(_session_state.get("transcript", []))
            if len(transcript) >= 5:
                try:
                    result = await run_contradiction_check(transcript[-30:])
                    if result and result.get("found") and result.get("confidence", 0) > 0.7:
                        summary = result.get("summary", "Contradiction detected.")
                        await session.generate_reply(
                            instructions=("Politely interject with this observation: " + summary)
                        )
                except Exception as exc:
                    logger.error(
                        "Contradiction monitor failed (%s): %s",
                        type(exc).__name__,
                        exc,
                    )
            await asyncio.sleep(20)

    # --- Background decision capture ---
    async def monitor_decisions() -> None:
        """Periodically check transcript for decisions."""
        from war_room_copilot.graph.nodes.capture_decision import (
            run_decision_check,
        )

        await asyncio.sleep(15)  # wait for some conversation
        last_checked = 0
        while True:
            async with _state_lock:
                transcript = list(_session_state.get("transcript", []))
            new_lines = transcript[last_checked:]
            if len(new_lines) >= 2:
                try:
                    result = await run_decision_check(new_lines[-5:])
                    if result and result.get("found"):
                        decision = result["decision"]
                        speaker = result.get("speaker", "Someone")
                        ts = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")
                        entry = f"[{ts}] {speaker}: {decision}"
                        async with _state_lock:
                            _session_state["decisions"].append(entry)
                            _session_state["decisions"] = _trim_list(
                                _session_state["decisions"], _MAX_DECISIONS
                            )
                        await session.generate_reply(
                            instructions=(
                                "Briefly confirm you logged this "
                                "decision: " + decision + ". Ask if that is correct."
                            )
                        )
                except Exception as exc:
                    logger.error(
                        "Decision monitor failed (%s): %s",
                        type(exc).__name__,
                        exc,
                    )
                last_checked = len(transcript)
            await asyncio.sleep(25)

    # --- Backboard.io cross-session memory ---
    backboard_thread_id: str | None = None
    try:
        from war_room_copilot.tools.backboard import (
            create_incident_thread,
            store_memory,
        )

        backboard_thread_id = await asyncio.wait_for(
            create_incident_thread(ctx.room.name), timeout=10.0
        )
        logger.info("Backboard thread: %s", backboard_thread_id)
        # Inject thread ID into session state so recall_node can find it
        _session_state["backboard_thread_id"] = backboard_thread_id
    except asyncio.TimeoutError:
        logger.warning("Backboard timed out after 10s — running without cross-session memory")
    except Exception as exc:
        logger.warning(
            "Backboard unavailable (%s): %s — running without cross-session memory",
            type(exc).__name__,
            exc,
        )

    async def sync_to_backboard() -> None:
        """Periodically flush findings/decisions to Backboard."""
        if not backboard_thread_id:
            return
        last_synced_d = 0
        last_synced_f = 0
        while True:
            await asyncio.sleep(60)
            async with _state_lock:
                decisions = list(_session_state.get("decisions", []))
                findings = list(_session_state.get("findings", []))
            new_decisions = decisions[last_synced_d:]
            new_findings = findings[last_synced_f:]
            for item in new_decisions + new_findings:
                try:
                    await store_memory(backboard_thread_id, item)
                except Exception as exc:
                    logger.error(
                        "Failed to sync to Backboard (%s): %s",
                        type(exc).__name__,
                        exc,
                    )
            last_synced_d = len(decisions)
            last_synced_f = len(findings)

    # --- Dashboard API server ---
    async def start_dashboard_api() -> None:
        """Start the FastAPI SSE server as a background task."""
        import uvicorn  # type: ignore[import-untyped]

        from war_room_copilot.api.main import app as api_app
        from war_room_copilot.api.main import set_state_ref

        set_state_ref(_session_state)
        config = uvicorn.Config(
            api_app,
            host="0.0.0.0",
            port=8000,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        try:
            await server.serve()
        except OSError as exc:
            logger.error(
                "Dashboard API failed to start (%s): %s — port 8000 may be in use",
                type(exc).__name__,
                exc,
            )
        except Exception as exc:
            logger.error(
                "Dashboard API crashed (%s): %s",
                type(exc).__name__,
                exc,
            )

    # --- Backchanneling (natural conversation UX) ---
    _backchannel_idx = 0

    async def backchannel_monitor() -> None:
        """Produce short acknowledgments during long monologues.

        If the same speaker has been talking for >20 seconds without
        the agent responding, emit a brief backchannel utterance to
        signal active listening.  Avoids interrupting and rotates
        through phrases so it doesn't sound robotic.
        """
        nonlocal _backchannel_idx
        import random

        last_backchannel_time = time.time()
        await asyncio.sleep(20)  # wait for conversation to start
        while True:
            async with _state_lock:
                structured = list(
                    _session_state.get("transcript_structured", [])
                )
            now = time.time()
            if len(structured) >= 3:
                # Check if last 3+ entries are from the same speaker
                # and span >20s without agent response
                recent = structured[-5:]
                speakers = {e["speaker"] for e in recent}
                if (
                    len(speakers) == 1
                    and "agent" not in next(iter(speakers)).lower()
                    and (now - last_backchannel_time) > 20
                ):
                    earliest = recent[0].get("epoch", now)
                    if now - earliest > 20:
                        phrase = _BACKCHANNEL_PHRASES[
                            _backchannel_idx % len(_BACKCHANNEL_PHRASES)
                        ]
                        _backchannel_idx += 1
                        try:
                            await session.generate_reply(
                                instructions=(
                                    f"Say only '{phrase}' — nothing "
                                    "more. Do not elaborate."
                                )
                            )
                            last_backchannel_time = time.time()
                        except Exception as exc:
                            logger.debug(
                                "Backchannel failed: %s", exc
                            )
            # Jitter to avoid predictable timing
            await asyncio.sleep(15 + random.uniform(0, 5))

    _launch_task(capture_voiceprints(), name="capture_voiceprints")
    _launch_task(monitor_contradictions(), name="monitor_contradictions")
    _launch_task(monitor_decisions(), name="monitor_decisions")
    _launch_task(sync_to_backboard(), name="sync_to_backboard")
    _launch_task(start_dashboard_api(), name="start_dashboard_api")
    _launch_task(backchannel_monitor(), name="backchannel_monitor")

    await disconnect_event.wait()
    logger.info("Room disconnected, entrypoint exiting")


class LiveKitPlatform:
    """MeetingPlatform backed by the LiveKit Agents framework.

    LiveKit owns the full audio pipeline (VAD -> STT -> LLM -> TTS) via
    AgentSession.  ``run()`` delegates to LiveKit's CLI runner which
    manages the event loop and worker lifecycle.
    """

    def run(self) -> None:
        """Start the LiveKit agent worker (blocking, manages own event loop)."""
        agents.cli.run_app(
            agents.WorkerOptions(
                entrypoint_fnc=_entrypoint,
                prewarm_fnc=_prewarm,
                # Keep num_idle_processes at 1 for reliability.
                # Note: orphaned local `dev` mode processes can register as ghost
                # workers with the Docker LiveKit server, stealing jobs. If the
                # agent fails to connect, check `lsof -i :7880` and kill any
                # stale Python processes from previous dev runs.
                num_idle_processes=1,
            )
        )

    async def shutdown(self) -> None:
        await close_mcp_client()
