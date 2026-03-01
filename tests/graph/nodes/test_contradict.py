"""Tests for contradiction detection — run_contradiction_check and contradict_node."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage

from tests.conftest import make_incident_state
from war_room_copilot.graph.nodes.contradict import (
    contradict_node,
    run_contradiction_check,
)

# ── run_contradiction_check ───────────────────────────────────────────────────


async def test_contradiction_check_too_few_lines() -> None:
    """Fewer than 3 lines returns None without calling LLM."""
    assert await run_contradiction_check([]) is None
    assert await run_contradiction_check(["a"]) is None
    assert await run_contradiction_check(["a", "b"]) is None


async def test_contradiction_check_valid_json() -> None:
    """Valid JSON from LLM is parsed correctly."""
    expected = {"found": True, "confidence": 0.9, "summary": "Conflicting times"}
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content=json.dumps(expected))

    with patch("war_room_copilot.graph.nodes.contradict.get_graph_llm", return_value=mock_llm):
        result = await run_contradiction_check(["a", "b", "c"])

    assert result == expected


async def test_contradiction_check_markdown_fences_stripped() -> None:
    """Markdown code fences are stripped before JSON parsing."""
    inner = {"found": False}
    text = f"```json\n{json.dumps(inner)}\n```"
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content=text)

    with patch("war_room_copilot.graph.nodes.contradict.get_graph_llm", return_value=mock_llm):
        result = await run_contradiction_check(["x", "y", "z"])

    assert result == {"found": False}


async def test_contradiction_check_invalid_json() -> None:
    """Invalid JSON from LLM returns None."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="not json at all")

    with patch("war_room_copilot.graph.nodes.contradict.get_graph_llm", return_value=mock_llm):
        result = await run_contradiction_check(["a", "b", "c"])

    assert result is None


async def test_contradiction_check_llm_exception() -> None:
    """LLM exception returns None."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = RuntimeError("timeout")

    with patch("war_room_copilot.graph.nodes.contradict.get_graph_llm", return_value=mock_llm):
        result = await run_contradiction_check(["a", "b", "c"])

    assert result is None


# ── contradict_node ───────────────────────────────────────────────────────────


async def test_contradict_node_high_confidence() -> None:
    """Confidence > 0.7 and found=true appends contradiction to findings."""
    mock_result = {"found": True, "confidence": 0.9, "summary": "Deploy time conflict"}

    with patch(
        "war_room_copilot.graph.nodes.contradict.run_contradiction_check",
        return_value=mock_result,
    ):
        state = make_incident_state(transcript=["a", "b", "c"])
        result = await contradict_node(state)

    assert "Contradiction detected" in result["findings"][0]
    assert isinstance(result["messages"][0], AIMessage)


async def test_contradict_node_low_confidence() -> None:
    """Confidence <= 0.7 returns no-contradiction message."""
    mock_result = {"found": True, "confidence": 0.5, "summary": "Maybe something"}

    with patch(
        "war_room_copilot.graph.nodes.contradict.run_contradiction_check",
        return_value=mock_result,
    ):
        result = await contradict_node(make_incident_state(transcript=["a", "b", "c"]))

    assert "No clear contradictions" in result["messages"][0].content
    assert "findings" not in result


async def test_contradict_node_not_found() -> None:
    """found=false returns no-contradiction message."""
    with patch(
        "war_room_copilot.graph.nodes.contradict.run_contradiction_check",
        return_value={"found": False},
    ):
        result = await contradict_node(make_incident_state(transcript=["a", "b", "c"]))

    assert "No clear contradictions" in result["messages"][0].content


async def test_contradict_node_none_result() -> None:
    """None result (too few lines) returns no-contradiction message."""
    with patch(
        "war_room_copilot.graph.nodes.contradict.run_contradiction_check",
        return_value=None,
    ):
        result = await contradict_node(make_incident_state())

    assert "No clear contradictions" in result["messages"][0].content
