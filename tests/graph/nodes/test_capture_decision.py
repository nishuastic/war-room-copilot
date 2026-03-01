"""Tests for decision capture — run_decision_check function."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from war_room_copilot.graph.nodes.capture_decision import run_decision_check

_PATCH_TARGET = "war_room_copilot.graph.nodes.capture_decision.get_graph_llm"

# ── run_decision_check ────────────────────────────────────────────────────────


async def test_decision_check_empty_list() -> None:
    """Empty transcript returns None without calling LLM."""
    assert await run_decision_check([]) is None


async def test_decision_check_valid_json() -> None:
    """Valid JSON with found=true is returned as a dict."""
    expected = {
        "found": True,
        "decision": "Roll back to v2.3",
        "speaker": "Alice",
        "type": "action",
    }
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content=json.dumps(expected))

    with patch(_PATCH_TARGET, return_value=mock_llm):
        result = await run_decision_check(["Alice: let's roll back to v2.3"])

    assert result == expected


async def test_decision_check_markdown_fences_stripped() -> None:
    """Markdown code fences are stripped before JSON parsing."""
    inner = {"found": False}
    text = f"```\n{json.dumps(inner)}\n```"
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content=text)

    with patch(_PATCH_TARGET, return_value=mock_llm):
        result = await run_decision_check(["Bob: just monitoring"])

    assert result == {"found": False}


async def test_decision_check_invalid_json() -> None:
    """Invalid JSON returns None."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="I think there was a decision about...")

    with patch(_PATCH_TARGET, return_value=mock_llm):
        result = await run_decision_check(["Alice: maybe we should roll back"])

    assert result is None


async def test_decision_check_llm_exception() -> None:
    """LLM exception returns None."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = RuntimeError("timeout")

    with patch(_PATCH_TARGET, return_value=mock_llm):
        result = await run_decision_check(["Alice: roll back now"])

    assert result is None
