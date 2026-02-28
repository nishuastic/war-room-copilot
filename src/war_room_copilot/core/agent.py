"""LiveKit agent with Speechmatics STT, ElevenLabs TTS, GitHub tools, and incident reasoning."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession, RoomInputOptions, StopResponse, llm
from livekit.plugins import elevenlabs, openai, silero, speechmatics
from livekit.plugins.speechmatics import (
    AdditionalVocabEntry,
    OperatingPoint,
    SpeakerIdentifier,
    TurnDetectionMode,
)

from ..config import (
    AGENT_PROMPT_FILE,
    DATA_DIR,
    ELEVENLABS_VOICE_ID,
    FOCUS_SPEAKERS,
    GITHUB_ALLOWED_REPOS,
    K8S_DICTIONARY_FILE,
    LLM_MODEL,
    SPEAKERS_FILE,
    VOICEPRINT_CAPTURE_INTERVAL,
    VOICEPRINT_INITIAL_DELAY,
    WAKE_WORD,
)
from ..models import SpeakerMetadata
from ..tools.github import (
    get_blame,
    get_commit_diff,
    get_recent_commits,
    list_pull_requests,
    read_file,
    search_code,
    search_issues,
)

load_dotenv()

logger = logging.getLogger("war-room-copilot")

RESERVED_LABEL = re.compile(r"^S\d+$")


def load_known_speakers() -> list[SpeakerMetadata]:
    if not SPEAKERS_FILE.exists():
        return []
    with open(SPEAKERS_FILE) as f:
        data = json.load(f)
    return [
        SpeakerMetadata(label=e["label"], speaker_identifiers=e["speaker_identifiers"])
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
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SPEAKERS_FILE, "w") as f:
            json.dump(data, f, indent=2)


def load_agent_prompt(room_name: str, known_speakers: list[SpeakerMetadata]) -> str:
    if AGENT_PROMPT_FILE.exists():
        template = AGENT_PROMPT_FILE.read_text()
    else:
        template = (
            "You are War Room Copilot, an AI assistant in a production incident call. "
            "Room: {room_name}. Known speakers: {known_speakers}. Be concise."
        )
    speaker_names = ", ".join(s.label for s in known_speakers) if known_speakers else "none yet"
    allowed_repos = ", ".join(GITHUB_ALLOWED_REPOS) if GITHUB_ALLOWED_REPOS else "none configured"
    return template.format(
        room_name=room_name,
        known_speakers=speaker_names,
        allowed_repos=allowed_repos,
    )


def load_custom_vocab() -> list[AdditionalVocabEntry]:
    if not K8S_DICTIONARY_FILE.exists():
        return []
    with open(K8S_DICTIONARY_FILE) as f:
        data = json.load(f)
    return [AdditionalVocabEntry(**entry) for entry in data.get("additional_vocab", [])]


def to_speaker_identifiers(speakers: list[SpeakerMetadata]) -> list[SpeakerIdentifier]:
    return [
        SpeakerIdentifier(label=s.label, speaker_identifiers=s.speaker_identifiers)
        for s in speakers
    ]


class WarRoomAgent(Agent):  # type: ignore[misc]
    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions)
        self._buffer: list[str] = []

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        text = (new_message.text_content or "").lower()
        if WAKE_WORD not in text:
            self._buffer.append(new_message.text_content or "")
            raise StopResponse()

        # Wake word detected — prepend buffered context
        if self._buffer:
            context_summary = "\n".join(self._buffer)
            turn_ctx.add_message(
                role="user",
                content=f"[Recent conversation context]\n{context_summary}",
            )
            self._buffer.clear()


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()

    room_name = ctx.room.name or "unknown"
    logger.info("Room: %s", room_name)

    known_speakers = load_known_speakers()
    prompt = load_agent_prompt(room_name, known_speakers)
    custom_vocab = load_custom_vocab()

    stt = speechmatics.STT(
        turn_detection_mode=TurnDetectionMode.SMART_TURN,
        operating_point=OperatingPoint.ENHANCED,
        enable_diarization=True,
        additional_vocab=custom_vocab,
        speaker_active_format="<{speaker_id}>{text}</{speaker_id}>",
        speaker_passive_format="<PASSIVE><{speaker_id}>{text}</{speaker_id}></PASSIVE>",
        focus_speakers=FOCUS_SPEAKERS,
        known_speakers=to_speaker_identifiers(known_speakers),
    )

    github_tools = [
        search_code,
        get_recent_commits,
        get_commit_diff,
        list_pull_requests,
        search_issues,
        read_file,
        get_blame,
    ]

    session = AgentSession(
        stt=stt,
        llm=openai.LLM(model=LLM_MODEL),
        tts=elevenlabs.TTS(voice_id=ELEVENLABS_VOICE_ID),
        vad=silero.VAD.load(
            min_silence_duration=0.3,
            prefix_padding_duration=0.3,
            activation_threshold=0.45,
        ),
        tools=github_tools,
    )

    await session.start(
        room=ctx.room,
        agent=WarRoomAgent(instructions=prompt),
        room_input_options=RoomInputOptions(),
    )

    async def capture_voiceprints() -> None:
        await asyncio.sleep(VOICEPRINT_INITIAL_DELAY)
        while True:
            try:
                result = await stt.get_speaker_ids()
                if result:
                    save_speakers(result)
            except Exception:
                pass
            await asyncio.sleep(VOICEPRINT_CAPTURE_INTERVAL)

    asyncio.create_task(capture_voiceprints())


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
