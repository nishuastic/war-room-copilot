"""Backboard.io client — cross-session memory for the war room agent.

Backboard provides persistent memory across incident sessions, ranked
#1 on LoCoMo and LongMemEval benchmarks.  Memory is automatically
extracted from messages and made searchable across threads.
"""

from __future__ import annotations

import logging
from typing import Any

from war_room_copilot.config import get_settings

logger = logging.getLogger("war-room-copilot.tools.backboard")

_client: Any = None
_assistant_id: str | None = None


async def get_backboard_client() -> tuple[Any, str]:
    """Return a connected Backboard client and assistant ID.

    Creates the assistant on first call; reuses on subsequent calls.
    """
    global _client, _assistant_id  # noqa: PLW0603
    if _client is not None and _assistant_id is not None:
        return _client, _assistant_id

    from backboard import BackboardClient  # type: ignore[import-untyped]

    cfg = get_settings()
    if not cfg.backboard_api_key:
        raise RuntimeError("BACKBOARD_API_KEY not set")

    _client = BackboardClient(api_key=cfg.backboard_api_key)

    assistant = await _client.create_assistant(
        name="War Room Copilot",
        system_prompt=(
            "You are an SRE incident response agent. Remember all "
            "decisions made during incidents. Track speaker identities, "
            "findings, and timelines. When asked about past incidents, "
            "recall relevant context."
        ),
        embedding_provider="openai",
        embedding_model_name="text-embedding-3-large",
        embedding_dims=3072,
    )
    _assistant_id = assistant.assistant_id
    return _client, _assistant_id


async def create_incident_thread(room_name: str) -> str:
    """Create a new Backboard thread keyed by room name."""
    client, assistant_id = await get_backboard_client()
    thread = await client.create_thread(assistant_id)
    logger.info("Backboard thread for room %s: %s", room_name, thread.thread_id)
    return thread.thread_id  # type: ignore[no-any-return]


async def store_memory(thread_id: str, content: str) -> None:
    """Store a message with automatic memory extraction."""
    client, _ = await get_backboard_client()
    await client.add_message(
        thread_id=thread_id,
        content=content,
        memory="Auto",
    )


async def recall_memory(thread_id: str, query: str) -> str:
    """Query Backboard memory for relevant past context."""
    client, _ = await get_backboard_client()
    response = await client.add_message(
        thread_id=thread_id,
        content=f"Recall anything relevant to: {query}",
        memory="Auto",
    )
    return str(response.content)
