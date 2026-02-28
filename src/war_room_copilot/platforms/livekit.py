"""LiveKit platform implementation."""

from __future__ import annotations

import asyncio
import logging

from livekit import agents
from livekit.agents import Agent, AgentSession, RoomInputOptions
from livekit.plugins import elevenlabs, openai, silero, speechmatics
from livekit.plugins.speechmatics import SpeakerIdentifier, TurnDetectionMode

from war_room_copilot.platforms.base import (
    SpeakerInfo,
    load_agent_prompt,
    load_known_speakers,
    save_speakers,
)

logger = logging.getLogger("war-room-copilot.platforms.livekit")


def _to_livekit_speakers(speakers: list[SpeakerInfo]) -> list[SpeakerIdentifier]:
    """Convert platform-agnostic SpeakerInfo to LiveKit's SpeakerIdentifier."""
    return [
        SpeakerIdentifier(label=s.label, speaker_identifiers=s.speaker_identifiers)
        for s in speakers
    ]


class WarRoomAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=load_agent_prompt())


async def _entrypoint(ctx: agents.JobContext) -> None:
    """LiveKit agent entrypoint — joins room, wires audio pipeline, runs."""
    await ctx.connect()
    logger.info("Room: %s", ctx.room.name)

    known_speakers = load_known_speakers()
    lk_speakers = _to_livekit_speakers(known_speakers)

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
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=elevenlabs.TTS(voice_id="21m00Tcm4TlvDq8ikWAM"),
        vad=silero.VAD.load(),
    )

    await session.start(
        room=ctx.room,
        agent=WarRoomAgent(),
        room_input_options=RoomInputOptions(),
    )

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
        pass
