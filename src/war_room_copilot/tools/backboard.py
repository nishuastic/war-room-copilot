"""Backboard.io client — cross-session memory for the war room agent.

Backboard provides persistent memory across incident sessions, ranked
#1 on LoCoMo and LongMemEval benchmarks.  Memory is automatically
extracted from messages and made searchable across threads.
"""

from __future__ import annotations

import logging
from typing import Any

from war_room_copilot.config import get_settings
from war_room_copilot.tools.github_mcp import (
    BackboardAuthError,
    BackboardConnectionError,
    BackboardError,
)

logger = logging.getLogger("war-room-copilot.tools.backboard")

_client: Any = None
_assistant_id: str | None = None


def _classify_backboard_error(exc: Exception) -> BackboardError:
    """Classify a raw Backboard exception into a specific error subtype."""
    msg = str(exc).lower()
    if any(kw in msg for kw in ("unauthorized", "401", "api key", "authentication")):
        return BackboardAuthError(
            f"Backboard authentication failed — check BACKBOARD_API_KEY: {exc}"
        )
    if any(kw in msg for kw in ("connection", "timeout", "unreachable", "dns")):
        return BackboardConnectionError(f"Backboard API unreachable: {exc}")
    return BackboardError(f"Backboard API error: {exc}")


async def get_backboard_client() -> tuple[Any, str]:
    """Return a connected Backboard client and assistant ID.

    Creates the assistant on first call; reuses on subsequent calls.

    Raises:
        BackboardAuthError: If BACKBOARD_API_KEY is missing or invalid.
        BackboardConnectionError: If the Backboard API is unreachable.
        BackboardError: For other Backboard API failures.
    """
    global _client, _assistant_id  # noqa: PLW0603
    if _client is not None and _assistant_id is not None:
        return _client, _assistant_id

    from backboard import BackboardClient  # type: ignore[import-untyped]

    cfg = get_settings()
    if not cfg.backboard_api_key:
        raise BackboardAuthError("BACKBOARD_API_KEY not set — cross-session memory is unavailable")

    try:
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
        logger.info("Backboard assistant ready: %s", _assistant_id)
        return _client, _assistant_id
    except BackboardError:
        _client = None
        _assistant_id = None
        raise
    except Exception as exc:
        _client = None
        _assistant_id = None
        raise _classify_backboard_error(exc) from exc


async def create_incident_thread(room_name: str) -> str:
    """Create a new Backboard thread keyed by room name.

    Raises:
        BackboardError: If thread creation fails.
    """
    try:
        client, assistant_id = await get_backboard_client()
        thread = await client.create_thread(assistant_id)
        logger.info(
            "Backboard thread for room %s: %s",
            room_name,
            thread.thread_id,
        )
        return thread.thread_id  # type: ignore[no-any-return]
    except BackboardError:
        raise
    except Exception as exc:
        raise _classify_backboard_error(exc) from exc


async def store_memory(thread_id: str, content: str) -> None:
    """Store a message with automatic memory extraction.

    Raises:
        BackboardError: If the store operation fails.
    """
    try:
        client, _ = await get_backboard_client()
        await client.add_message(
            thread_id=thread_id,
            content=content,
            memory="Auto",
        )
    except BackboardError:
        raise
    except Exception as exc:
        bb_err = _classify_backboard_error(exc)
        logger.error(
            "Failed to store memory (%s): %s",
            type(bb_err).__name__,
            bb_err,
        )
        raise bb_err from exc


async def recall_memory(thread_id: str, query: str) -> str:
    """Query Backboard memory for relevant past context.

    Raises:
        BackboardError: If the recall operation fails.
    """
    try:
        client, _ = await get_backboard_client()
        response = await client.add_message(
            thread_id=thread_id,
            content=f"Recall anything relevant to: {query}",
            memory="Auto",
        )
        return str(response.content)
    except BackboardError:
        raise
    except Exception as exc:
        bb_err = _classify_backboard_error(exc)
        logger.error(
            "Failed to recall memory (%s): %s",
            type(bb_err).__name__,
            bb_err,
        )
        raise bb_err from exc
