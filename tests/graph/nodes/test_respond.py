"""Tests for respond node — general conversation with context."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage

from tests.conftest import make_incident_state
from war_room_copilot.graph.nodes.respond import respond_node

# ── respond_node ──────────────────────────────────────────────────────────────


async def test_respond_basic() -> None:
    """Returns AIMessage with LLM content."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="Here is the answer.")

    state = make_incident_state(query="what is happening?")

    with patch("war_room_copilot.graph.nodes.respond.get_graph_llm", return_value=mock_llm):
        result = await respond_node(state)

    assert isinstance(result["messages"][0], AIMessage)
    assert result["messages"][0].content == "Here is the answer."


async def test_respond_appends_context() -> None:
    """Findings and decisions are appended to the system prompt."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="ok")

    state = make_incident_state(
        query="what do we know?",
        findings=["DB latency is 500ms"],
        decisions=["Roll back to v2.3"],
    )

    with patch("war_room_copilot.graph.nodes.respond.get_graph_llm", return_value=mock_llm):
        await respond_node(state)

    system_msg = mock_llm.ainvoke.call_args[0][0][0]
    assert "Incident context:" in system_msg.content
    assert "DB latency" in system_msg.content
    assert "Roll back" in system_msg.content


async def test_respond_no_context() -> None:
    """Without findings/decisions, system prompt has no context section."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="hello")

    state = make_incident_state(query="hi there")

    with patch("war_room_copilot.graph.nodes.respond.get_graph_llm", return_value=mock_llm):
        await respond_node(state)

    system_msg = mock_llm.ainvoke.call_args[0][0][0]
    assert "Incident context:" not in system_msg.content


async def test_respond_truncates_findings() -> None:
    """Only last 5 findings are used in context."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="noted")

    findings = [f"finding_{i}" for i in range(10)]
    state = make_incident_state(query="summarize", findings=findings)

    with patch("war_room_copilot.graph.nodes.respond.get_graph_llm", return_value=mock_llm):
        await respond_node(state)

    system_msg = mock_llm.ainvoke.call_args[0][0][0]
    assert "finding_5" in system_msg.content  # last 5 includes index 5-9
    assert "finding_0" not in system_msg.content


async def test_respond_llm_exception_fallback() -> None:
    """LLM failure returns graceful fallback."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = RuntimeError("LLM down")

    state = make_incident_state(query="help")

    with patch("war_room_copilot.graph.nodes.respond.get_graph_llm", return_value=mock_llm):
        result = await respond_node(state)

    assert "trouble responding" in result["messages"][0].content
