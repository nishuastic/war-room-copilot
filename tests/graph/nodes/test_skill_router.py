"""Tests for skill router node — intent classification."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import make_incident_state
from war_room_copilot.graph.nodes.skill_router import skill_router_node

# ── skill_router_node ─────────────────────────────────────────────────────────


async def test_skill_router_empty_query_no_llm_call() -> None:
    """Empty query returns 'respond' without calling LLM."""
    with patch("war_room_copilot.graph.nodes.skill_router.get_graph_llm") as mock_get:
        result = await skill_router_node(make_incident_state(query=""))
    assert result["routed_skill"] == "respond"
    mock_get.assert_not_called()


async def test_skill_router_valid_skill_returned() -> None:
    """LLM returning a valid skill name is used as-is."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="  Investigate\n")

    with patch("war_room_copilot.graph.nodes.skill_router.get_graph_llm", return_value=mock_llm):
        result = await skill_router_node(make_incident_state(query="look at the code"))

    assert result["routed_skill"] == "investigate"


async def test_skill_router_unknown_skill_defaults_respond() -> None:
    """Unknown skill from LLM defaults to 'respond'."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="banana")

    with patch("war_room_copilot.graph.nodes.skill_router.get_graph_llm", return_value=mock_llm):
        result = await skill_router_node(make_incident_state(query="do something"))

    assert result["routed_skill"] == "respond"


async def test_skill_router_llm_exception_defaults_respond() -> None:
    """LLM failure defaults to 'respond'."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = RuntimeError("LLM down")

    with patch("war_room_copilot.graph.nodes.skill_router.get_graph_llm", return_value=mock_llm):
        result = await skill_router_node(make_incident_state(query="help"))

    assert result["routed_skill"] == "respond"


async def test_skill_router_uses_last_5_messages() -> None:
    """Only the last 5 messages are passed to the LLM."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="respond")

    messages = [MagicMock() for _ in range(10)]
    state = make_incident_state(query="test", messages=messages)

    with patch("war_room_copilot.graph.nodes.skill_router.get_graph_llm", return_value=mock_llm):
        await skill_router_node(state)

    call_messages = mock_llm.ainvoke.call_args[0][0]
    # First message is ROUTER_SYSTEM_PROMPT, then last 5 from history
    assert len(call_messages) == 6
