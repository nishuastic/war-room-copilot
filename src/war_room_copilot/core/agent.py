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

# Silence noisy debug logs from third-party libraries
for _logger_name in (
    "livekit",
    "livekit.agents",
    "livekit.rtc",
    "livekit.plugins",
    "livekit.plugins.speechmatics",
    "aiosqlite",
    "speechmatics",
    "httpx",
    "httpcore",
    "asyncio",
):
    logging.getLogger(_logger_name).setLevel(logging.WARNING)

from livekit import agents
from livekit.agents import Agent, AgentSession, RoomInputOptions, StopResponse, llm
from livekit.plugins import openai, silero, speechmatics
from livekit.plugins.speechmatics import (
    AdditionalVocabEntry,
    OperatingPoint,
    SpeakerIdentifier,
    TurnDetectionMode,
)

from ..config import (
    AGENT_PROMPT_FILE,
    CONFIDENCE_DASHBOARD,
    CONFIDENCE_SPEAK,
    DATA_DIR,
    DB_FILE,
    FOCUS_SPEAKERS,
    GITHUB_ALLOWED_REPOS,
    K8S_DICTIONARY_FILE,
    LLM_MODEL,
    SHORT_TERM_WINDOW_SIZE,
    SKILL_LLM_MODELS,
    SPEAKERS_FILE,
    SPEECHMATICS_TTS_VOICE,
    VOICEPRINT_CAPTURE_INTERVAL,
    VOICEPRINT_INITIAL_DELAY,
    WAKE_WORD,
    WAKE_WORD_BUFFER,
)
from ..memory import DecisionTracker, IncidentDB, LongTermMemory, ShortTermMemory
from ..models import SpeakerMetadata, TranscriptSegment
from ..skills import SKILL_PROMPTS, SkillResult, SkillRouter
from ..skills.investigation import run_investigation
from ..skills.models import Skill
from ..tools.datadog import (
    get_datadog_monitors,
    query_datadog_apm,
    query_datadog_logs,
    query_datadog_metrics,
)
from ..tools.github import (
    close_pull_request,
    create_github_issue,
    get_blame,
    get_commit_diff,
    get_recent_commits,
    list_pull_requests,
    read_file,
    revert_commit,
    search_code,
    search_issues,
)
from ..tools.logs import (
    query_aks_logs,
    query_azure_monitor,
    query_cloudwatch_logs,
    query_ecs_logs,
    query_gcp_logs,
    query_gke_pod_logs,
    query_lambda_logs,
)
from ..tools.recall import recall_decision, set_memory_context
from ..tools.runbook import search_runbook
from ..tools.service_graph import get_service_dependencies, get_service_graph, get_service_health

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
    # Load existing data to preserve custom labels
    existing: dict[str, dict[str, Any]] = {}
    if SPEAKERS_FILE.exists():
        with open(SPEAKERS_FILE) as f:
            for entry in json.load(f):
                for sid in entry.get("speaker_identifiers", []):
                    existing[sid] = entry

    data = []
    seen_labels: set[str] = set()
    for speaker in raw_speakers:
        if isinstance(speaker, dict):
            label, ids = speaker.get("label", ""), speaker.get("speaker_identifiers", [])
        else:
            label, ids = speaker.label, speaker.speaker_identifiers
        if not (label and ids):
            continue
        if RESERVED_LABEL.match(label):
            label = f"Speaker_{label[1:]}"
        # If any identifier matches an existing entry, use its label
        for sid in ids:
            if sid in existing and not RESERVED_LABEL.match(existing[sid]["label"]):
                label = existing[sid]["label"]
                break
        if label not in seen_labels:
            data.append({"label": label, "speaker_identifiers": ids})
            seen_labels.add(label)
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
    """Parse Speechmatics tagged text into a TranscriptSegment (first segment)."""
    segments = parse_all_segments(raw_text)
    if segments:
        return segments[0]
    return TranscriptSegment(
        speaker_id="unknown",
        text=raw_text.strip(),
        timestamp=time.time(),
        is_passive=False,
    )


def parse_all_segments(raw_text: str) -> list[TranscriptSegment]:
    """Parse ALL speaker segments from Speechmatics tagged text."""
    now = time.time()
    segments: list[TranscriptSegment] = []

    # Extract passive segments with their speaker tags
    for passive_match in PASSIVE_WRAP.finditer(raw_text):
        inner = passive_match.group(1)
        for tag_match in SPEAKER_TAG.finditer(inner):
            text = tag_match.group(2).strip()
            if text:
                segments.append(
                    TranscriptSegment(
                        speaker_id=tag_match.group(1),
                        text=text,
                        timestamp=now,
                        is_passive=True,
                    )
                )

    # Extract active segments (everything outside <PASSIVE> tags)
    active = PASSIVE_WRAP.sub("", raw_text)
    for tag_match in SPEAKER_TAG.finditer(active):
        text = tag_match.group(2).strip()
        if text:
            segments.append(
                TranscriptSegment(
                    speaker_id=tag_match.group(1),
                    text=text,
                    timestamp=now,
                    is_passive=False,
                )
            )

    return segments


class WarRoomAgent(Agent):
    def __init__(
        self,
        instructions: str,
        memory: ShortTermMemory,
        decision_tracker: DecisionTracker | None,
        db: IncidentDB,
        session_id: int,
        long_term: LongTermMemory | None,
        router: SkillRouter,
    ) -> None:
        super().__init__(instructions=instructions)
        self._base_instructions = instructions
        self._memory = memory
        self._decision_tracker = decision_tracker
        self._db = db
        self._session_id = session_id
        self._long_term = long_term
        self._router = router
        self._wake_ts: float | None = None
        # Wake word sentence buffer — collects segments for WAKE_WORD_BUFFER seconds
        self._wake_buffer: list[str] = []
        self._wake_buffer_speaker: str = ""
        self._wake_buffer_timer: asyncio.Task[None] | None = None
        # Async background skill state (investigate)
        self._pending_result: str | None = None
        self._async_task: asyncio.Task[None] | None = None

    async def _run_silent_skill(
        self, context: str, user_message: str, skill_result: SkillResult
    ) -> None:
        """Run a skill via Backboard outside the LiveKit pipeline (medium confidence path)."""
        if self._long_term is None:
            logger.warning("Silent skill skipped — no Backboard connection")
            return

        skill_prompt = SKILL_PROMPTS.get(skill_result.skill, "")
        prompt = (
            f"{skill_prompt}\n\n"
            f"Context:\n{context}\n\n"
            f"User said: {user_message}\n\n"
            "Provide a concise analysis."
        )
        provider, model = SKILL_LLM_MODELS.get(skill_result.skill.value, ("openai", LLM_MODEL))

        try:
            response = await self._long_term.store(prompt, send_to_llm=True)
            await self._db.add_trace(
                self._session_id,
                "silent_skill_response",
                {
                    "skill": skill_result.skill.value,
                    "confidence": skill_result.confidence,
                    "reasoning": skill_result.reasoning,
                    "llm_provider": provider,
                    "model": model,
                    "response": (response or "")[:1000],
                },
            )
            logger.info("Silent skill (%s) response written to trace", skill_result.skill.value)
        except Exception:
            logger.exception("Silent skill failed for %s", skill_result.skill.value)

    async def _run_async_skill_background(self, context: str, user_message: str) -> None:
        """Run investigate asynchronously and notify when done."""
        logger.info("Background investigate started for: %s", user_message)
        try:
            result = await run_investigation(context, user_message)
            self._pending_result = result
            logger.info("Background investigate complete (%d chars)", len(result))
            self.session.say(
                "Done investigating. Let me know when you want me to share my findings."
            )
        except Exception:
            logger.exception("Background investigate failed")
            self._pending_result = "The investigation ran into an error. Try asking me again."
            try:
                self.session.say(
                    "I hit an issue during the investigation. Ask me again for what I found."
                )
            except Exception:
                pass

    def _process_transcript(self, raw_text: str) -> list[TranscriptSegment]:
        """Log, store, and track all transcript segments. Returns parsed segments."""
        _log_transcript(raw_text)

        all_segments = parse_all_segments(raw_text)
        primary = parse_transcript(raw_text)

        # Store primary segment in short-term memory and SQLite
        self._memory.add(primary)
        asyncio.create_task(self._db.add_segment(self._session_id, primary))

        # Store ALL segments in Backboard long-term memory (non-blocking)
        if self._long_term is not None:
            for seg in all_segments:
                asyncio.create_task(self._long_term.store(f"[{seg.speaker_id}] {seg.text}"))

        # Check for decisions across all segments (non-blocking)
        if self._decision_tracker is not None:
            for seg in all_segments:
                asyncio.create_task(self._decision_tracker.check_for_decision(seg))

        return all_segments

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        raw_text = new_message.text_content or ""

        # Transcript storage is handled by user_input_transcribed event handler.
        # Parse segments here only for wake word detection and buffer management.
        all_segments = parse_all_segments(raw_text)

        # If buffer is active, append all segment texts (continuation of wake word sentence)
        if self._wake_buffer_timer is not None and not self._wake_buffer_timer.done():
            for seg in all_segments:
                self._wake_buffer.append(seg.text)
            logger.info("Wake buffer: appended %d segment(s)", len(all_segments))
            raise StopResponse()

        # Wake word check — scan ALL segments, not just the first one
        wake_segment: TranscriptSegment | None = None
        for seg in all_segments:
            if WAKE_WORD in seg.text.lower():
                wake_segment = seg
                break

        if wake_segment is None:
            raise StopResponse()

        # Wake word detected — record timestamp for latency tracking
        self._wake_ts = time.time()
        asyncio.create_task(
            self._db.add_trace(
                self._session_id,
                "wake_word",
                {"text": wake_segment.text, "speaker_id": wake_segment.speaker_id},
            )
        )

        # Collect ALL text from ALL segments for context (not just the wake word segment)
        all_text = " ".join(seg.text for seg in all_segments)

        # Start sentence buffer — wait for continuation segments before routing
        self._wake_buffer = [all_text]
        self._wake_buffer_speaker = wake_segment.speaker_id
        self._wake_buffer_timer = asyncio.create_task(self._flush_wake_buffer())
        logger.info("Wake buffer: started (%.2fs window)", WAKE_WORD_BUFFER)
        raise StopResponse()

    async def _flush_wake_buffer(self) -> None:
        """Wait for the buffer window, then route and process the combined text."""
        await asyncio.sleep(WAKE_WORD_BUFFER)

        combined_text = " ".join(self._wake_buffer)
        speaker = self._wake_buffer_speaker
        self._wake_buffer = []
        self._wake_buffer_speaker = ""

        logger.info("Wake buffer flushed: '%s'", combined_text)

        # --- Deliver pending async result if one is ready ---
        if self._pending_result is not None:
            result = self._pending_result
            self._pending_result = None
            logger.info("Delivering pending async result (%d chars)", len(result))
            try:
                await self.session.say(result)
            except Exception:
                logger.exception("Failed to deliver async result")
            return

        # --- Notify if async task is still running ---
        if self._async_task is not None and not self._async_task.done():
            logger.info("Async skill still running — notifying user")
            try:
                self.session.say("Still on it, I'll let you know when I'm done.")
            except Exception:
                pass
            return

        # --- Skill routing ---
        await self.update_instructions(self._base_instructions)

        context = self._memory.format_context()
        skill_result = await self._router.classify(context, combined_text)

        # Log skill route trace
        asyncio.create_task(
            self._db.add_trace(
                self._session_id,
                "skill_route",
                {
                    "skill": skill_result.skill.value,
                    "confidence": skill_result.confidence,
                    "reasoning": skill_result.reasoning,
                    "text": combined_text,
                },
            )
        )

        # Confidence gating
        if skill_result.confidence < CONFIDENCE_DASHBOARD:
            return

        if skill_result.confidence < CONFIDENCE_SPEAK:
            asyncio.create_task(self._run_silent_skill(context, combined_text, skill_result))
            return

        # --- INVESTIGATE: say "on it", then run in background ---
        if skill_result.skill == Skill.INVESTIGATE:
            logger.info(
                "investigate skill — starting background task for: %s",
                combined_text,
            )
            try:
                await self.session.say("On it, give me a moment to dig into this.")
            except Exception:
                logger.exception("Failed to say 'on it'")
            self._async_task = asyncio.create_task(
                self._run_async_skill_background(context, combined_text)
            )
            return

        # --- All other skills: apply skill prompt and generate reply ---
        skill_prompt = SKILL_PROMPTS.get(skill_result.skill, "")
        if skill_prompt:
            await self.update_instructions(self._base_instructions + skill_prompt)

        # Skills that must look up real data: force the LLM to call at least one tool.
        # GENERAL/IDEATE are left as "auto" since they may not need tool calls.
        _tool_choice: str = (
            "required"
            if skill_result.skill in (Skill.INVESTIGATE, Skill.DEBUG, Skill.RECALL)
            else "auto"
        )

        try:
            logger.info(
                "Generating reply for: [%s] %s (tool_choice=%s)",
                speaker,
                combined_text,
                _tool_choice,
            )
            handle = self.session.generate_reply(
                user_input=f"[{speaker}] {combined_text}",
                tool_choice=_tool_choice,  # type: ignore[arg-type]
            )
            logger.info("generate_reply returned handle %s", handle.id)
            await handle
            logger.info("Speech playout complete for handle %s", handle.id)
        except RuntimeError:
            logger.error(
                "generate_reply failed (speech scheduling likely paused) — speech not delivered"
            )
        except Exception:
            logger.exception("Unexpected error in generate_reply")


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

            # Inject cross-session context into the agent's system prompt
            past_context = await long_term.get_session_context()
            if past_context:
                prompt += (
                    f"\n\n[MEMORY FROM PAST SESSIONS]\n{past_context}\n\n"
                    "When relevant, proactively reference past session context. "
                    "Example: 'In a previous session, the team decided to roll back Redis to v6...'"
                )
                asyncio.create_task(
                    db.add_trace(session_id, "memory_loaded", {"context": past_context[:2000]})
                )
                logger.info("Injected past session context into system prompt")

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
        # GitHub — read
        search_code,
        get_recent_commits,
        get_commit_diff,
        list_pull_requests,
        search_issues,
        read_file,
        get_blame,
        # GitHub — write (requires 'repo' scope on GITHUB_TOKEN)
        create_github_issue,
        revert_commit,
        close_pull_request,
        # Memory
        recall_decision,
        # Runbooks
        search_runbook,
        # Service graph
        get_service_graph,
        get_service_dependencies,
        get_service_health,
        # Datadog monitoring
        query_datadog_metrics,
        query_datadog_logs,
        query_datadog_apm,
        get_datadog_monitors,
        # AWS logs
        query_cloudwatch_logs,
        query_ecs_logs,
        query_lambda_logs,
        # GCP logs
        query_gcp_logs,
        query_gke_pod_logs,
        # Azure logs
        query_azure_monitor,
        query_aks_logs,
    ]

    session: AgentSession[Any] = AgentSession(
        stt=stt,
        llm=openai.LLM(model=LLM_MODEL),
        tts=speechmatics.TTS(voice=SPEECHMATICS_TTS_VOICE),
        vad=silero.VAD.load(
            min_silence_duration=0.3,
            prefix_padding_duration=0.3,
            activation_threshold=0.45,
        ),
        tools=tools,
        max_tool_steps=7,
        # Require at least 4 words before allowing an interruption.
        # Prevents the user's own follow-up phrases (e.g. "Talking to you")
        # from cutting off Sam's reply before it even starts.
        min_interruption_words=4,
    )

    router = SkillRouter()

    war_room_agent = WarRoomAgent(
        instructions=prompt,
        memory=memory,
        decision_tracker=decision_tracker,
        db=db,
        session_id=session_id,
        long_term=long_term,
        router=router,
    )

    await session.start(
        room=ctx.room,
        agent=war_room_agent,
        room_input_options=RoomInputOptions(),
    )

    # Trace tool calls and LLM responses via session events
    @session.on("function_tools_executed")  # type: ignore[arg-type]
    def _on_tools_executed(ev: Any) -> None:
        asyncio.create_task(db.update_metrics(session_id, llm_calls=1))
        for call, output in ev.zipped():
            tool_name = getattr(call, "name", str(call))
            raw_args = getattr(call, "arguments", {})
            result_preview = str(getattr(output, "output", ""))[:300] if output else ""
            logger.info("Tool call: %s(%s) → %s", tool_name, raw_args, result_preview[:100])
            asyncio.create_task(
                db.add_trace(
                    session_id,
                    "tool_call",
                    {"tool": tool_name, "args": raw_args, "result": result_preview},
                )
            )

    @session.on("agent_speech_committed")  # type: ignore[arg-type]
    def _on_agent_speech(msg: Any) -> None:
        text = getattr(msg, "content", None) or str(msg)
        if text:
            text_str = str(text)[:1000]
            # Compute latency from wake word to first agent speech
            latency_ms = 0.0
            if war_room_agent._wake_ts is not None:
                latency_ms = (time.time() - war_room_agent._wake_ts) * 1000
                war_room_agent._wake_ts = None
                asyncio.create_task(
                    db.add_trace(
                        session_id,
                        "latency",
                        {"ms": round(latency_ms, 1)},
                    )
                )
            asyncio.create_task(db.add_trace(session_id, "llm_response", {"text": text_str}))
            asyncio.create_task(
                db.add_segment(
                    session_id,
                    TranscriptSegment(speaker_id="sam", text=text_str, timestamp=time.time()),
                )
            )
            # Track TTS chars for cost
            asyncio.create_task(
                db.update_metrics(
                    session_id,
                    tts_chars=len(text_str),
                    latency_ms=latency_ms,
                )
            )

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev: Any) -> None:
        """Fires for ALL final transcripts regardless of scheduling state.

        This ensures transcripts are logged, stored in memory/SQLite/Backboard,
        and checked for decisions even when speech scheduling is paused
        (e.g. during interruptions).  The event fires per-segment (not per-turn),
        so each invocation typically contains one tagged segment.
        """
        # Only process final transcripts (skip interim/partial)
        if not getattr(ev, "is_final", False):
            return
        raw_text = getattr(ev, "transcript", "") or ""
        if not raw_text.strip():
            return
        # Delegate to agent's transcript processing (log + store + track)
        war_room_agent._process_transcript(raw_text)

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
        # Post-mortem interview mode: ask structured questions via TTS
        try:
            postmortem_questions = [
                "What was the root cause of this incident?",
                "What was the impact on users or systems?",
                "What follow-up actions are needed to prevent recurrence?",
            ]
            for question in postmortem_questions:
                await session.say(question, allow_interruptions=True)
                await asyncio.sleep(15)  # Wait for verbal response
        except RuntimeError as e:
            # AgentSession may already be stopped by the time on_shutdown fires
            logger.debug("Post-mortem interview skipped: %s", e)
        except Exception:
            logger.exception("Post-mortem interview failed")

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
