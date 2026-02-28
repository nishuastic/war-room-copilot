"""LiveKit agent with memory, decision tracking, GitHub tools, and incident reasoning."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
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
    DB_FILE,
    ELEVENLABS_VOICE_ID,
    FOCUS_SPEAKERS,
    GITHUB_ALLOWED_REPOS,
    K8S_DICTIONARY_FILE,
    LLM_MODEL,
    SHORT_TERM_WINDOW_SIZE,
    SPEAKERS_FILE,
    VOICEPRINT_CAPTURE_INTERVAL,
    VOICEPRINT_INITIAL_DELAY,
    WAKE_WORD,
)
from ..memory import DecisionTracker, IncidentDB, LongTermMemory, ShortTermMemory
from ..models import SpeakerMetadata, TranscriptSegment
from ..tools.github import (
    get_blame,
    get_commit_diff,
    get_recent_commits,
    list_pull_requests,
    read_file,
    search_code,
    search_issues,
)
from ..tools.recall import recall_decision, set_memory_context

load_dotenv()

logger = logging.getLogger("war-room-copilot")

RESERVED_LABEL = re.compile(r"^S\d+$")
SPEAKER_TAG = re.compile(r"<(\w+)>(.*?)</\1>", re.DOTALL)
PASSIVE_WRAP = re.compile(r"<PASSIVE>(.*?)</PASSIVE>", re.DOTALL)


def _log_transcript(raw: str) -> None:
    """Log each speaker's text using a per-speaker logger named ``transcript.<label>``."""
    # Passive segments first
    for passive_match in PASSIVE_WRAP.finditer(raw):
        inner = SPEAKER_TAG.search(passive_match.group(1))
        if inner:
            spk = inner.group(1)
            logging.getLogger(f"transcript.{spk}").info(
                "[%s] (passive) %s", spk, inner.group(2).strip()
            )
    # Active segments
    active = PASSIVE_WRAP.sub("", raw)
    for m in SPEAKER_TAG.finditer(active):
        spk = m.group(1)
        logging.getLogger(f"transcript.{spk}").info("[%s] %s", spk, m.group(2).strip())


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


def parse_transcript(raw_text: str) -> TranscriptSegment:
    """Parse Speechmatics tagged text into a TranscriptSegment."""
    is_passive = bool(PASSIVE_WRAP.search(raw_text))
    inner = PASSIVE_WRAP.sub(r"\1", raw_text)
    match = SPEAKER_TAG.search(inner)
    if match:
        speaker_id = match.group(1)
        text = match.group(2).strip()
    else:
        speaker_id = "unknown"
        text = inner.strip()
    return TranscriptSegment(
        speaker_id=speaker_id,
        text=text,
        timestamp=time.time(),
        is_passive=is_passive,
    )


class WarRoomAgent(Agent):  # type: ignore[misc]
    def __init__(
        self,
        instructions: str,
        memory: ShortTermMemory,
        decision_tracker: DecisionTracker | None,
        db: IncidentDB,
        session_id: int,
        long_term: LongTermMemory | None,
    ) -> None:
        super().__init__(instructions=instructions)
        self._memory = memory
        self._decision_tracker = decision_tracker
        self._db = db
        self._session_id = session_id
        self._long_term = long_term

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        raw_text = new_message.text_content or ""
        _log_transcript(raw_text)
        segment = parse_transcript(raw_text)

        # Store in short-term memory and SQLite
        self._memory.add(segment)
        asyncio.create_task(self._db.add_segment(self._session_id, segment))

        # Store in Backboard long-term memory (non-blocking)
        if self._long_term is not None:
            asyncio.create_task(self._long_term.store(f"[{segment.speaker_id}] {segment.text}"))

        # Check for decisions (non-blocking)
        if self._decision_tracker is not None:
            asyncio.create_task(self._decision_tracker.check_for_decision(segment))

        # Wake word check
        if WAKE_WORD not in segment.text.lower():
            raise StopResponse()

        # Wake word detected — emit trace event
        asyncio.create_task(
            self._db.add_trace(
                self._session_id,
                "wake_word",
                {"text": segment.text, "speaker_id": segment.speaker_id},
            )
        )

        # Inject buffered context
        context = self._memory.format_context()
        if context:
            turn_ctx.add_message(
                role="user",
                content=f"[Recent conversation context]\n{context}",
            )
            self._memory.clear()


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()

    room_name = ctx.room.name or "unknown"
    logger.info("Room: %s", room_name)

    known_speakers = load_known_speakers()
    prompt = load_agent_prompt(room_name, known_speakers)
    custom_vocab = load_custom_vocab()

    # Initialize SQLite
    db = IncidentDB(DB_FILE)
    await db.initialize()
    session_id = await db.start_session(room_name)
    logger.info("DB session: %d", session_id)

    # Initialize short-term memory
    memory = ShortTermMemory(SHORT_TERM_WINDOW_SIZE)

    # Initialize long-term memory (Backboard) — optional
    long_term: LongTermMemory | None = None
    decision_tracker: DecisionTracker | None = None
    backboard_key = os.environ.get("BACKBOARD_API_KEY")

    if backboard_key:
        try:
            long_term = LongTermMemory(backboard_key)
            await long_term.initialize()
            await long_term.start_session(room_name)
            logger.info("Backboard long-term memory initialized")

            decision_tracker = DecisionTracker(
                short_term=memory,
                long_term=long_term,
                db=db,
                session_id=session_id,
                backboard_api_key=backboard_key,
            )
            await decision_tracker.initialize()
            logger.info("Decision tracker initialized")
        except Exception:
            logger.exception("Failed to initialize Backboard — continuing without long-term memory")
            long_term = None
            decision_tracker = None
    else:
        logger.warning("BACKBOARD_API_KEY not set — long-term memory disabled")

    # Set up recall tool context
    set_memory_context(db, long_term, session_id)  # type: ignore[arg-type]

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

    tools: list[Any] = [
        search_code,
        get_recent_commits,
        get_commit_diff,
        list_pull_requests,
        search_issues,
        read_file,
        get_blame,
        recall_decision,
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
        tools=tools,
        max_tool_steps=7,
    )

    war_room_agent = WarRoomAgent(
        instructions=prompt,
        memory=memory,
        decision_tracker=decision_tracker,
        db=db,
        session_id=session_id,
        long_term=long_term,
    )

    await session.start(
        room=ctx.room,
        agent=war_room_agent,
        room_input_options=RoomInputOptions(),
    )

    # Trace tool calls and LLM responses via session events
    @session.on("function_calls_collected")  # type: ignore[misc]
    def _on_tool_calls(calls: Any) -> None:
        for call in calls if isinstance(calls, list) else [calls]:
            tool_name = getattr(call, "function_name", str(call))
            raw_args = getattr(call, "arguments", {})
            asyncio.create_task(
                db.add_trace(session_id, "tool_call", {"tool": tool_name, "args": raw_args})
            )

    @session.on("function_calls_finished")  # type: ignore[misc]
    def _on_tool_results(calls: Any) -> None:
        for call in calls if isinstance(calls, list) else [calls]:
            tool_name = getattr(call, "function_name", str(call))
            result_preview = str(getattr(call, "result", ""))[:500]
            asyncio.create_task(
                db.add_trace(
                    session_id, "tool_result", {"tool": tool_name, "result": result_preview}
                )
            )

    @session.on("agent_speech_committed")  # type: ignore[misc]
    def _on_agent_speech(msg: Any) -> None:
        text = getattr(msg, "content", None) or str(msg)
        if text:
            text_str = str(text)[:1000]
            asyncio.create_task(db.add_trace(session_id, "llm_response", {"text": text_str}))
            asyncio.create_task(
                db.add_segment(
                    session_id,
                    TranscriptSegment(speaker_id="sam", text=text_str, timestamp=time.time()),
                )
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

    async def on_shutdown() -> None:
        await db.end_session(session_id)
        if decision_tracker:
            await decision_tracker.close()
        if long_term:
            await long_term.close()
        await db.close()
        logger.info("Session %d ended, resources cleaned up", session_id)

    ctx.add_shutdown_callback(on_shutdown)


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
