"""Tests for summarize node — pure helpers and LLM-calling node."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from tests.conftest import make_incident_state
from war_room_copilot.graph.nodes.summarize import (
    SUMMARIZE_SYSTEM_PROMPT,
    TIMELINE_SYSTEM_PROMPT,
    _wants_timeline,
    summarize_node,
)

# ── _wants_timeline (pure) ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "query,expected",
    [
        ("show me the timeline", True),
        ("what happened when", True),
        ("chronological order please", True),
        ("time line of events", True),
        ("sequence of events so far", True),
        ("TIMELINE PLEASE", True),  # case insensitive
        ("summarize the incident", False),
        ("", False),
        ("what time is it", False),
    ],
)
def test_wants_timeline(query: str, expected: bool) -> None:
    """Keyword matching for timeline detection."""
    assert _wants_timeline(query) is expected


# ── summarize_node ────────────────────────────────────────────────────────────


async def test_summarize_no_context_early_return() -> None:
    """Empty state returns canned message without calling LLM."""
    state = make_incident_state()
    result = await summarize_node(state)
    assert "No incident data" in result["findings"][0]
    assert isinstance(result["messages"][0], AIMessage)


async def test_summarize_with_transcript() -> None:
    """LLM is called and response appears in findings and messages."""
    mock_llm = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = "Summary: server was down for 30 minutes."
    mock_llm.ainvoke.return_value = mock_response

    state = make_incident_state(
        transcript=["10:00 Alice: database is slow"],
        query="summarize",
    )

    with patch("war_room_copilot.graph.nodes.summarize.get_graph_llm", return_value=mock_llm):
        result = await summarize_node(state)

    assert result["findings"][0] == "Summary: server was down for 30 minutes."
    mock_llm.ainvoke.assert_called_once()


async def test_summarize_uses_timeline_prompt() -> None:
    """Timeline query selects TIMELINE_SYSTEM_PROMPT."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="timeline")

    state = make_incident_state(
        transcript=["10:00 Alice: alert fired"],
        query="show me the timeline",
    )

    with patch("war_room_copilot.graph.nodes.summarize.get_graph_llm", return_value=mock_llm):
        await summarize_node(state)

    messages = mock_llm.ainvoke.call_args[0][0]
    assert messages[0] is TIMELINE_SYSTEM_PROMPT


async def test_summarize_uses_summary_prompt() -> None:
    """Non-timeline query selects SUMMARIZE_SYSTEM_PROMPT."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="summary")

    state = make_incident_state(
        transcript=["10:00 Alice: alert fired"],
        query="what happened so far",
    )

    with patch("war_room_copilot.graph.nodes.summarize.get_graph_llm", return_value=mock_llm):
        await summarize_node(state)

    messages = mock_llm.ainvoke.call_args[0][0]
    assert messages[0] is SUMMARIZE_SYSTEM_PROMPT


async def test_summarize_truncates_transcript() -> None:
    """Only the last 20 transcript lines are sent to the LLM."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="summary")

    lines = [f"line {i}" for i in range(30)]
    state = make_incident_state(transcript=lines, query="summarize")

    with patch("war_room_copilot.graph.nodes.summarize.get_graph_llm", return_value=mock_llm):
        await summarize_node(state)

    content = mock_llm.ainvoke.call_args[0][0][1].content
    assert "line 10" in content  # line 10 is at index 10 → in last 20
    assert "line 0" not in content  # line 0 is truncated


async def test_summarize_llm_exception_fallback() -> None:
    """LLM failure returns a graceful fallback message."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = RuntimeError("LLM down")

    state = make_incident_state(
        transcript=["10:00 something happened"],
        query="summarize",
    )

    with patch("war_room_copilot.graph.nodes.summarize.get_graph_llm", return_value=mock_llm):
        result = await summarize_node(state)

    assert "Unable to generate summary" in result["findings"][0]
