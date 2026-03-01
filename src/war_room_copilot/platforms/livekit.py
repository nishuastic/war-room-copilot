"""LiveKit platform implementation."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from livekit import agents
from livekit.agents import Agent, AgentSession, RoomInputOptions, RunContext, function_tool
from livekit.plugins import elevenlabs, silero, speechmatics  # noqa: F401
from livekit.plugins.speechmatics import SpeakerIdentifier, TurnDetectionMode

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

# Persistent state shared across graph invocations within a session.
# This accumulates transcript, findings, and decisions over the lifetime
# of the agent — giving the graph memory across multiple tool calls.
_session_state: dict[str, Any] = {
    "transcript": [],
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

    stt = speechmatics.STT(
        turn_detection_mode=TurnDetectionMode.SMART_TURN,
        enable_diarization=True,
        speaker_active_format="<{speaker_id}>{text}</{speaker_id}>",
        speaker_passive_format="<PASSIVE><{speaker_id}>{text}</{speaker_id}></PASSIVE>",
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

    # --- P0-B: Feed STT transcript into session state ---
    @session.on("user_input_transcribed")
    def _on_transcript(event: Any) -> None:
        if not getattr(event, "is_final", False):
            return
        text = getattr(event, "transcript", "").strip()
        if not text:
            return
        speaker = getattr(event, "speaker_id", None) or "Unknown"
        # Map raw speaker ID to known name if available
        display_name = _session_state["speakers"].get(speaker, speaker)
        ts = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")
        line = f"[{ts}] {display_name}: {text}"
        _session_state["transcript"].append(line)
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

    asyncio.create_task(capture_voiceprints())


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
