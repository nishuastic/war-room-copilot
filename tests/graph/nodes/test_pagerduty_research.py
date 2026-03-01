"""Tests for PagerDuty research node — MCP-calling node with parallel fetch."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage

from tests.conftest import make_incident_state
from war_room_copilot.graph.nodes.pagerduty_research import pagerduty_research_node
from war_room_copilot.tools.github_mcp import WarRoomToolError


# ── pagerduty_research_node ──────────────────────────────────────────────────


async def test_pagerduty_research_empty_query() -> None:
    """Empty query returns empty dict without calling MCP."""
    state = make_incident_state(query="")
    result = await pagerduty_research_node(state)
    assert result == {}


async def test_pagerduty_research_mcp_connection_error() -> None:
    """MCP connection failure returns error finding."""
    state = make_incident_state(query="who is on call")

    with patch(
        "war_room_copilot.graph.nodes.pagerduty_research.get_pd_client",
        side_effect=WarRoomToolError("PagerDuty MCP not running"),
    ):
        result = await pagerduty_research_node(state)

    assert len(result["findings"]) == 1
    assert "[PagerDuty] Could not connect" in result["findings"][0]
    # Result should include an AIMessage
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], AIMessage)


async def test_pagerduty_research_successful_results() -> None:
    """Both incident fetch and on-call results are included in findings."""
    mock_client = AsyncMock()

    incidents_text = "PagerDuty Active Incidents (1):\n  #42 [triggered/high] DB down"
    oncall_text = "PagerDuty On-Call (1 entries):\n  L1: Jane Doe -- Primary Schedule"

    state = make_incident_state(query="active incidents")

    with (
        patch(
            "war_room_copilot.graph.nodes.pagerduty_research.get_pd_client",
            return_value=mock_client,
        ),
        patch(
            "war_room_copilot.graph.nodes.pagerduty_research._safe_get_incidents",
            return_value=incidents_text,
        ),
        patch(
            "war_room_copilot.graph.nodes.pagerduty_research._safe_get_oncall",
            return_value=oncall_text,
        ),
    ):
        result = await pagerduty_research_node(state)

    findings_text = result["findings"][0]
    assert "DB down" in findings_text
    assert "Jane Doe" in findings_text
    assert isinstance(result["messages"][0], AIMessage)


async def test_pagerduty_research_one_fetch_fails_other_succeeds() -> None:
    """When one fetch raises, its error is appended but the other succeeds."""
    mock_client = AsyncMock()

    oncall_text = "PagerDuty On-Call (1 entries):\n  L1: John Smith -- Primary"

    state = make_incident_state(query="who is on call")

    with (
        patch(
            "war_room_copilot.graph.nodes.pagerduty_research.get_pd_client",
            return_value=mock_client,
        ),
        patch(
            "war_room_copilot.graph.nodes.pagerduty_research._safe_get_incidents",
            side_effect=RuntimeError("API timeout"),
        ),
        patch(
            "war_room_copilot.graph.nodes.pagerduty_research._safe_get_oncall",
            return_value=oncall_text,
        ),
    ):
        result = await pagerduty_research_node(state)

    findings_text = result["findings"][0]
    # The successful on-call result should be present
    assert "John Smith" in findings_text
    # The failed incident fetch should have an error entry
    assert "Error" in findings_text
