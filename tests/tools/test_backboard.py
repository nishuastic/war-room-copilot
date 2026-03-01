"""Tests for Backboard.io client — cross-session memory."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import war_room_copilot.tools.backboard as bb_mod
from war_room_copilot.tools.backboard import (
    get_backboard_client,
    recall_memory,
    store_memory,
)

# ── get_backboard_client ──────────────────────────────────────────────────────


async def test_get_backboard_client_no_api_key() -> None:
    """Missing BACKBOARD_API_KEY raises RuntimeError."""
    mock_settings = MagicMock()
    mock_settings.backboard_api_key = ""

    mock_bb = MagicMock()

    with (
        patch("war_room_copilot.tools.backboard.get_settings", return_value=mock_settings),
        patch.dict("sys.modules", {"backboard": mock_bb}),
    ):
        with pytest.raises(RuntimeError, match="BACKBOARD_API_KEY not set"):
            await get_backboard_client()


async def test_get_backboard_client_caches() -> None:
    """Second call returns cached instance without creating a new assistant."""
    mock_client = AsyncMock()
    mock_assistant = MagicMock()
    mock_assistant.assistant_id = "asst-123"
    mock_client.create_assistant.return_value = mock_assistant

    mock_settings = MagicMock()
    mock_settings.backboard_api_key = "test-key"

    mock_bb_module = MagicMock()
    mock_bb_module.BackboardClient.return_value = mock_client

    with (
        patch("war_room_copilot.tools.backboard.get_settings", return_value=mock_settings),
        patch.dict("sys.modules", {"backboard": mock_bb_module}),
    ):
        result1 = await get_backboard_client()
        result2 = await get_backboard_client()

    assert result1 == result2
    # create_assistant should only be called once
    mock_client.create_assistant.assert_called_once()


# ── store_memory ──────────────────────────────────────────────────────────────


async def test_store_memory_calls_add_message() -> None:
    """store_memory calls add_message with memory='Auto'."""
    mock_client = AsyncMock()
    bb_mod._client = mock_client
    bb_mod._assistant_id = "asst-123"

    await store_memory("thread-1", "DB is down")

    mock_client.add_message.assert_called_once_with(
        thread_id="thread-1",
        content="DB is down",
        memory="Auto",
    )


# ── recall_memory ─────────────────────────────────────────────────────────────


async def test_recall_memory_returns_content() -> None:
    """recall_memory returns str(response.content)."""
    mock_response = MagicMock()
    mock_response.content = "Past incident: DB pool exhaustion"

    mock_client = AsyncMock()
    mock_client.add_message.return_value = mock_response
    bb_mod._client = mock_client
    bb_mod._assistant_id = "asst-123"

    result = await recall_memory("thread-1", "database issues")

    assert result == "Past incident: DB pool exhaustion"
    mock_client.add_message.assert_called_once()
    call_kwargs = mock_client.add_message.call_args[1]
    assert "Recall anything relevant to: database issues" in call_kwargs["content"]
