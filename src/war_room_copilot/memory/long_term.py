"""Long-term memory via Backboard SDK — LLM routing + persistent memory."""

from __future__ import annotations

import json
import logging
from typing import Any

from backboard import BackboardClient
from backboard.exceptions import BackboardNotFoundError

from ..config import BACKBOARD_ASSISTANT_FILE, DATA_DIR, LLM_MODEL

logger = logging.getLogger("war-room-copilot")


class LongTermMemory:
    def __init__(self, api_key: str) -> None:
        self._client = BackboardClient(api_key=api_key)
        self._assistant_id: str | None = None
        self._thread_id: str | None = None

    async def initialize(self) -> None:
        """Load or create Backboard assistant (cached in .data/backboard_assistant.json)."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        if BACKBOARD_ASSISTANT_FILE.exists():
            with open(BACKBOARD_ASSISTANT_FILE) as f:
                data = json.load(f)
            candidate_id = data["assistant_id"]
            # Verify the assistant still exists before caching its ID
            try:
                await self._client.get_assistant(candidate_id)
                self._assistant_id = candidate_id
                logger.info("Loaded Backboard assistant: %s", self._assistant_id)
                return
            except BackboardNotFoundError:
                logger.warning("Cached Backboard assistant %s not found — recreating", candidate_id)
                BACKBOARD_ASSISTANT_FILE.unlink(missing_ok=True)

        assistant: Any = await self._client.create_assistant(
            name="War Room Copilot",
            system_prompt=(
                "You are the persistent memory for an engineering war room copilot. "
                "Prioritize remembering: engineering decisions and their rationale, "
                "incident root causes and resolutions, action items and owners, "
                "recurring patterns across incidents (e.g. 'Redis issues', 'deploy failures'), "
                "and team-specific context (services, infrastructure, on-call owners). "
                "Deprioritize: general discussion, filler conversation, unresolved speculation."
            ),
        )
        self._assistant_id = str(assistant.assistant_id)
        with open(BACKBOARD_ASSISTANT_FILE, "w") as f:
            json.dump({"assistant_id": self._assistant_id}, f)
        logger.info("Created Backboard assistant: %s", self._assistant_id)

    async def start_session(self, room_name: str) -> str:
        """Create new Backboard thread for this LiveKit session."""
        assert self._assistant_id is not None
        thread: Any = await self._client.create_thread(self._assistant_id)
        self._thread_id = str(thread.thread_id)
        # Store session context
        await self.store(f"[Session started] Room: {room_name}")
        logger.info("Started Backboard thread: %s", self._thread_id)
        return self._thread_id

    async def store(self, content: str, send_to_llm: bool = False) -> str | None:
        """Store content in Backboard memory.

        send_to_llm=False: ingestion only (transcript, decisions).
        send_to_llm=True: get an LLM response with memory context.
        """
        assert self._thread_id is not None
        if send_to_llm:
            response: Any = await self._client.add_message(
                thread_id=self._thread_id,
                content=content,
                llm_provider="openai",
                model_name=LLM_MODEL,
                memory="Auto",
                stream=False,
            )
            text = response.content or response.message or "" if response else ""
            return str(text) if text else None
        else:
            await self._client.add_memory(
                assistant_id=self._assistant_id,
                content=content,
            )
            return None

    async def recall(self, query: str) -> str:
        """Query Backboard with memory-augmented LLM response."""
        assert self._thread_id is not None
        response: Any = await self._client.add_message(
            thread_id=self._thread_id,
            content=query,
            llm_provider="openai",
            model_name=LLM_MODEL,
            memory="Auto",
            stream=False,
        )
        if not response:
            return "No relevant memories found."
        text = response.content or response.message or ""
        return str(text) if text else "No relevant memories found."

    async def get_session_context(self) -> str:
        """Query Backboard for relevant context from past sessions (read-only, fast)."""
        assert self._thread_id is not None
        try:
            response: Any = await self._client.add_message(
                thread_id=self._thread_id,
                content=(
                    "Summarize the most important decisions, incidents, and action items "
                    "from previous sessions. Focus on: recurring patterns, unresolved issues, "
                    "and key technical decisions. Be concise."
                ),
                llm_provider="openai",
                model_name=LLM_MODEL,
                memory="readonly",
                stream=False,
            )
            if not response:
                return ""
            text = response.content or response.message or ""
            return str(text) if text else ""
        except Exception:
            logger.warning("Failed to load past session context from Backboard", exc_info=True)
            return ""

    async def close(self) -> None:
        """Clean up client resources."""
        await self._client.aclose()
