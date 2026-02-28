"""Stage 0: LiveKit agent with Speechmatics STT, ElevenLabs TTS, and speaker identification."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession, RoomInputOptions
from livekit.plugins import elevenlabs, openai, silero, speechmatics
from livekit.plugins.speechmatics import SpeakerIdentifier, TurnDetectionMode

load_dotenv()

logger = logging.getLogger("war-room-copilot")

_PROJECT_ROOT = Path(__file__).parents[3]
SPEAKERS_FILE = _PROJECT_ROOT / "speakers.json"
RESERVED_LABEL = re.compile(r"^S\d+$")


def load_known_speakers() -> list[SpeakerIdentifier]:
    if not SPEAKERS_FILE.exists():
        return []
    with open(SPEAKERS_FILE) as f:
        data = json.load(f)
    return [
        SpeakerIdentifier(label=e["label"], speaker_identifiers=e["speaker_identifiers"])
        for e in data
        if e.get("label") and e.get("speaker_identifiers") and not RESERVED_LABEL.match(e["label"])
    ]


def save_speakers(raw_speakers: list[Any]) -> None:
    data = []
    for speaker in raw_speakers:
        if isinstance(speaker, dict):
            label, ids = speaker.get("label", ""), speaker.get("speaker_identifiers", [])
        else:
            label, ids = speaker.label, speaker.speaker_identifiers
        if label and ids:
            if RESERVED_LABEL.match(label):
                label = f"Speaker_{label[1:]}"
            data.append({"label": label, "speaker_identifiers": ids})
    if data:
        with open(SPEAKERS_FILE, "w") as f:
            json.dump(data, f, indent=2)


def load_agent_prompt() -> str:
    agent_file = _PROJECT_ROOT / "assets" / "agent.md"
    if agent_file.exists():
        return agent_file.read_text()
    return "You are War Room Copilot, an AI assistant in a production incident call. Be concise."


class WarRoomAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=load_agent_prompt())


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()

    logger.info("Room: %s", ctx.room.name)

    known_speakers = load_known_speakers()

    stt = speechmatics.STT(
        turn_detection_mode=TurnDetectionMode.SMART_TURN,
        enable_diarization=True,
        speaker_active_format="<{speaker_id}>{text}</{speaker_id}>",
        speaker_passive_format="<PASSIVE><{speaker_id}>{text}</{speaker_id}></PASSIVE>",
        focus_speakers=["S1"],
        known_speakers=known_speakers,
    )

    session = AgentSession(
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
            instructions=f"Greet the team. You recognize: {names}. Welcome them back by name. Be brief."
        )
    else:
        await session.generate_reply(
            instructions="Greet the team briefly. Say you are War Room Copilot and ready to listen."
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


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
