"""LiveKit platform implementation."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession,
    RoomInputOptions,
    RunContext,
    function_tool,
)
from livekit.plugins import elevenlabs, silero, speechmatics  # noqa: F401
from livekit.plugins.speechmatics import SpeakerIdentifier, TurnDetectionMode

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

logger = logging.getLogger("war-room-copilot.platforms.livekit")

# SRE/incident vocabulary for Speechmatics custom dictionary.
# Improves recognition of domain-specific terms that general STT misrecognizes.
INCIDENT_VOCAB = [
    {"content": "Kubernetes"},
    {"content": "kubectl", "sounds_like": ["kube-control", "kube-cuddle"]},
    {"content": "MTTR", "sounds_like": ["M T T R", "mean time to recovery"]},
    {"content": "MTTD", "sounds_like": ["M T T D", "mean time to detect"]},
    {"content": "PagerDuty"},
    {"content": "Datadog"},
    {"content": "Speechmatics"},
    {"content": "LangGraph"},
    {"content": "LiveKit"},
    {"content": "OpenTelemetry", "sounds_like": ["open telemetry"]},
    {"content": "Prometheus"},
    {"content": "Grafana"},
    {"content": "SLO", "sounds_like": ["S L O", "service level objective"]},
    {"content": "SLA", "sounds_like": ["S L A", "service level agreement"]},
    {"content": "RCA", "sounds_like": ["R C A", "root cause analysis"]},
    {"content": "postmortem"},
    {"content": "runbook"},
    {"content": "rollback"},
    {"content": "hotfix"},
    {"content": "canary deployment"},
    {"content": "war room"},
    {"content": "p zero", "sounds_like": ["P0", "priority zero"]},
    {"content": "p one", "sounds_like": ["P1", "priority one"]},
]

# Persistent state shared across graph invocations within a session.
# This accumulates transcript, findings, and decisions over the lifetime
# of the agent — giving the graph memory across multiple tool calls.
_session_state: dict[str, Any] = {
    "transcript": [],
    "transcript_structured": [],
    "findings": [],
    "decisions": [],
    "speakers": {},
    "messages": [],
}


def _to_livekit_speakers(speakers: list[SpeakerInfo]) -> list[SpeakerIdentifier]:
    """Convert platform-agnostic SpeakerInfo to LiveKit's SpeakerIdentifier."""
    return [
        SpeakerIdentifier(label=s.label, speaker_identifiers=s.speaker_identifiers)
        for s in speakers
    ]


async def _invoke_graph(query: str) -> str:
    """Run the incident graph with the current session state.

    The graph routes the query to the appropriate skill (investigate,
    summarize, recall, respond) and returns the final result text.
    State is accumulated across calls so the graph has memory.
    """
    input_state = {
        **_session_state,
        "query": query,
    }

    result = await incident_graph.ainvoke(input_state)

    # Persist accumulated state for next invocation
    _session_state["findings"] = result.get("findings", _session_state["findings"])
    _session_state["decisions"] = result.get("decisions", _session_state["decisions"])
    _session_state["messages"] = result.get("messages", _session_state["messages"])

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
    logger.info("reason_tool invoked: %s", query)
    return await _invoke_graph(query)


class WarRoomAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=load_agent_prompt(),
            tools=[reason_tool],
        )


async def _entrypoint(ctx: agents.JobContext) -> None:
    """LiveKit agent entrypoint — joins room, wires audio pipeline, runs."""
    await ctx.connect()
    logger.info("Room: %s", ctx.room.name)

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
        tts=elevenlabs.TTS(model="eleven_turbo_v2_5"),
        vad=silero.VAD.load(),
    )

    await session.start(
        room=ctx.room,
        agent=WarRoomAgent(),
        room_input_options=RoomInputOptions(),
    )

    # --- P0-B + P1-B: Feed STT transcript into session state ---
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
        # Structured entry for timeline generation (P1-B)
        _session_state["transcript_structured"].append(
            {
                "speaker": display_name,
                "text": text,
                "timestamp": ts,
                "epoch": time.time(),
            }
        )
        logger.debug("Transcript: %s", line)

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
            except Exception:
                pass
            await asyncio.sleep(30)

    # --- P1-A: Background contradiction monitoring ---
    async def monitor_contradictions() -> None:
        """Periodically check transcript for contradictions."""
        from war_room_copilot.graph.nodes.contradict import (
            run_contradiction_check,
        )

        await asyncio.sleep(30)  # wait for transcript to accumulate
        while True:
            transcript = _session_state.get("transcript", [])
            if len(transcript) >= 5:
                try:
                    result = await run_contradiction_check(transcript[-30:])
                    if result and result.get("found") and result.get("confidence", 0) > 0.7:
                        summary = result.get("summary", "Contradiction detected.")
                        await session.generate_reply(
                            instructions=("Politely interject with this observation: " + summary)
                        )
                except Exception:
                    logger.exception("Contradiction check failed")
            await asyncio.sleep(20)

    # --- P1-C: Background decision capture ---
    async def monitor_decisions() -> None:
        """Periodically check transcript for decisions."""
        from war_room_copilot.graph.nodes.capture_decision import (
            run_decision_check,
        )

        await asyncio.sleep(15)  # wait for some conversation
        last_checked = 0
        while True:
            transcript = _session_state.get("transcript", [])
            new_lines = transcript[last_checked:]
            if len(new_lines) >= 2:
                try:
                    result = await run_decision_check(new_lines[-5:])
                    if result and result.get("found"):
                        decision = result["decision"]
                        speaker = result.get("speaker", "Someone")
                        ts = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")
                        entry = f"[{ts}] {speaker}: {decision}"
                        _session_state["decisions"].append(entry)
                        await session.generate_reply(
                            instructions=(
                                "Briefly confirm you logged this "
                                "decision: " + decision + ". Ask if that is correct."
                            )
                        )
                except Exception:
                    logger.exception("Decision check failed")
                last_checked = len(transcript)
            await asyncio.sleep(25)

    # --- P1-F: Backboard.io cross-session memory ---
    backboard_thread_id: str | None = None
    try:
        from war_room_copilot.tools.backboard import (
            create_incident_thread,
            store_memory,
        )

        backboard_thread_id = await create_incident_thread(ctx.room.name)
        logger.info("Backboard thread: %s", backboard_thread_id)
    except Exception:
        logger.warning("Backboard unavailable, running without cross-session memory")

    async def sync_to_backboard() -> None:
        """Periodically flush findings/decisions to Backboard."""
        if not backboard_thread_id:
            return
        last_synced_d = 0
        last_synced_f = 0
        while True:
            await asyncio.sleep(60)
            decisions = _session_state.get("decisions", [])
            findings = _session_state.get("findings", [])
            new_decisions = decisions[last_synced_d:]
            new_findings = findings[last_synced_f:]
            for item in new_decisions + new_findings:
                try:
                    await store_memory(backboard_thread_id, item)
                except Exception:
                    logger.exception("Failed to sync to Backboard")
            last_synced_d = len(decisions)
            last_synced_f = len(findings)

    # --- P1-G: Dashboard API server ---
    async def start_dashboard_api() -> None:
        """Start the FastAPI SSE server as a background task."""
        import uvicorn  # type: ignore[import-untyped]

        from war_room_copilot.api.main import app as api_app
        from war_room_copilot.api.main import set_state_ref

        set_state_ref(_session_state)
        config = uvicorn.Config(api_app, host="0.0.0.0", port=8000, log_level="warning")
        server = uvicorn.Server(config)
        await server.serve()

    asyncio.create_task(capture_voiceprints())
    asyncio.create_task(monitor_contradictions())
    asyncio.create_task(monitor_decisions())
    asyncio.create_task(sync_to_backboard())
    asyncio.create_task(start_dashboard_api())


class LiveKitPlatform:
    """MeetingPlatform backed by the LiveKit Agents framework.

    LiveKit owns the full audio pipeline (VAD → STT → LLM → TTS) via
    AgentSession.  ``run()`` delegates to LiveKit's CLI runner which
    manages the event loop and worker lifecycle.
    """

    def run(self) -> None:
        """Start the LiveKit agent worker (blocking, manages own event loop)."""
        agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=_entrypoint))

    async def shutdown(self) -> None:
        await close_mcp_client()
