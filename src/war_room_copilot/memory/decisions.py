"""LLM-based decision detection via Backboard."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from backboard import BackboardClient
from backboard.exceptions import BackboardNotFoundError

from ..config import (
    BACKBOARD_DECISION_ASSISTANT_FILE,
    DATA_DIR,
    DECISION_CHECK_INTERVAL,
    DECISION_CONFIDENCE_THRESHOLD,
    LLM_MODEL,
)
from ..models import Decision, TranscriptSegment
from .db import IncidentDB
from .long_term import LongTermMemory
from .short_term import ShortTermMemory

logger = logging.getLogger("war-room-copilot")

_DECISION_SYSTEM_PROMPT = (
    "You analyze conversation excerpts from production incident war rooms. "
    "Extract any decisions, action items, or agreements that were made. "
    "Respond ONLY with valid JSON. No other text."
)

_DECISION_USER_PROMPT = (
    "Analyze this conversation excerpt. If any decisions, action items, or agreements "
    "were made, extract them as JSON with this format:\n"
    '{"decisions": [{"text": "...", "speaker": "...", "confidence": 0.0-1.0}]}\n'
    'If no decisions were made, respond with: {"decisions": []}\n\n'
)


class DecisionTracker:
    def __init__(
        self,
        short_term: ShortTermMemory,
        long_term: LongTermMemory,
        db: IncidentDB,
        session_id: int,
        backboard_api_key: str,
    ) -> None:
        self._short_term = short_term
        self._long_term = long_term
        self._db = db
        self._session_id = session_id
        self._segments_since_check = 0
        self._lock = asyncio.Lock()
        self._client = BackboardClient(api_key=backboard_api_key)
        self._decision_assistant_id: str | None = None
        self._decision_thread_id: str | None = None

    async def _create_assistant(self) -> str:
        """Create a new Backboard decision assistant and cache its ID."""
        assistant: Any = await self._client.create_assistant(
            name="War Room Decision Extractor",
            system_prompt=_DECISION_SYSTEM_PROMPT,
        )
        assistant_id = str(assistant.assistant_id)
        with open(BACKBOARD_DECISION_ASSISTANT_FILE, "w") as f:
            json.dump({"assistant_id": assistant_id}, f)
        return assistant_id

    async def initialize(self) -> None:
        """Load or create the decision-extraction Backboard assistant."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        if BACKBOARD_DECISION_ASSISTANT_FILE.exists():
            with open(BACKBOARD_DECISION_ASSISTANT_FILE) as f:
                data = json.load(f)
            self._decision_assistant_id = data["assistant_id"]
        else:
            self._decision_assistant_id = await self._create_assistant()
            logger.info("Created decision assistant: %s", self._decision_assistant_id)

        try:
            thread: Any = await self._client.create_thread(self._decision_assistant_id)
        except BackboardNotFoundError:
            logger.warning(
                "Cached decision assistant %s not found — recreating",
                self._decision_assistant_id,
            )
            self._decision_assistant_id = await self._create_assistant()
            logger.info("Created decision assistant: %s", self._decision_assistant_id)
            thread = await self._client.create_thread(self._decision_assistant_id)

        self._decision_thread_id = str(thread.thread_id)
        logger.info("Decision tracker initialized (assistant=%s)", self._decision_assistant_id)

    async def check_for_decision(self, segment: TranscriptSegment) -> Decision | None:
        """Check if recent context contains a decision. Runs every N segments."""
        async with self._lock:
            self._segments_since_check += 1
            if self._segments_since_check < DECISION_CHECK_INTERVAL:
                return None
            self._segments_since_check = 0

        recent = self._short_term.get_recent(DECISION_CHECK_INTERVAL * 2)
        if not recent:
            return None

        context = "\n".join(f"[{s.speaker_id}] {s.text}" for s in recent)
        try:
            return await self._extract_decision(context, recent)
        except Exception:
            logger.exception("Decision extraction failed")
            return None

    async def _extract_decision(
        self, context: str, recent: list[TranscriptSegment]
    ) -> Decision | None:
        assert self._decision_thread_id is not None
        response: Any = await self._client.add_message(
            thread_id=self._decision_thread_id,
            content=f"{_DECISION_USER_PROMPT}{context}",
            llm_provider="openai",
            model_name=LLM_MODEL,
            memory="Auto",
            stream=False,
        )
        if not response:
            return None

        # MessageResponse has both .content and .message — try both
        raw = str(response.content or response.message or "").strip()
        if not raw:
            return None

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("Decision LLM returned non-JSON: %s", raw[:200])
            return None
        decisions_raw = data.get("decisions", [])
        if not decisions_raw:
            return None

        # Take the highest-confidence decision
        best: dict[str, Any] = max(decisions_raw, key=lambda d: d.get("confidence", 0))
        if best.get("confidence", 0) < DECISION_CONFIDENCE_THRESHOLD:
            return None

        decision = Decision(
            id=str(uuid.uuid4()),
            text=best["text"],
            speaker_id=best.get("speaker", "unknown"),
            timestamp=time.time(),
            context=context,
            confidence=best["confidence"],
        )

        await self._db.add_decision(self._session_id, decision)
        await self._long_term.store(
            f"[Decision] {decision.speaker_id}: {decision.text} "
            f"(confidence: {decision.confidence:.1f})"
        )
        logger.info("Decision detected: %s", decision.text)
        return decision

    async def get_decisions(self) -> list[Decision]:
        return await self._db.get_decisions(self._session_id)

    async def search_decisions(self, query: str) -> list[Decision]:
        return await self._db.search_decisions(query)

    async def close(self) -> None:
        await self._client.aclose()
