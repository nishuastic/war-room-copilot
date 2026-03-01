"""Tests for Sentry research node — MCP-calling node with parallel search."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage

from tests.conftest import make_incident_state
from war_room_copilot.graph.nodes.sentry_research import sentry_research_node
from war_room_copilot.tools.github_mcp import WarRoomToolError


# ── sentry_research_node ─────────────────────────────────────────────────────


async def test_sentry_research_empty_query() -> None:
    """Empty query returns empty dict without calling MCP."""
    state = make_incident_state(query="")
    result = await sentry_research_node(state)
    assert result == {}


async def test_sentry_research_mcp_connection_error() -> None:
    """MCP connection failure returns error finding."""
    state = make_incident_state(query="500 errors in checkout")

    with patch(
        "war_room_copilot.graph.nodes.sentry_research.get_sentry_client",
        side_effect=WarRoomToolError("Sentry MCP not running"),
    ):
        result = await sentry_research_node(state)

    assert len(result["findings"]) == 1
    assert "[Sentry] Could not connect" in result["findings"][0]
    # Result should include an AIMessage
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], AIMessage)


async def test_sentry_research_successful_results() -> None:
    """Both issue fetch and error search results are included in findings."""
    mock_client = AsyncMock()

    issues_text = "Sentry Issues (2):\n  - [ERROR] TimeoutError in db.py"
    search_text = "Sentry Issues (1):\n  - [WARNING] Slow query detected"

    state = make_incident_state(query="timeout errors")

    with (
        patch(
            "war_room_copilot.graph.nodes.sentry_research.get_sentry_client",
            return_value=mock_client,
        ),
        patch(
            "war_room_copilot.graph.nodes.sentry_research._safe_get_issues",
            return_value=issues_text,
        ),
        patch(
            "war_room_copilot.graph.nodes.sentry_research._safe_search_errors",
            return_value=search_text,
        ),
    ):
        result = await sentry_research_node(state)

    findings_text = result["findings"][0]
    assert "TimeoutError" in findings_text
    assert "Slow query" in findings_text
    assert isinstance(result["messages"][0], AIMessage)


async def test_sentry_research_one_search_fails_other_succeeds() -> None:
    """When one search raises, its error is appended but the other succeeds."""
    mock_client = AsyncMock()

    issues_text = "Sentry Issues (1):\n  - [ERROR] Connection reset"

    state = make_incident_state(query="connection errors")

    with (
        patch(
            "war_room_copilot.graph.nodes.sentry_research.get_sentry_client",
            return_value=mock_client,
        ),
        patch(
            "war_room_copilot.graph.nodes.sentry_research._safe_get_issues",
            return_value=issues_text,
        ),
        patch(
            "war_room_copilot.graph.nodes.sentry_research._safe_search_errors",
            side_effect=RuntimeError("search timeout"),
        ),
    ):
        result = await sentry_research_node(state)

    findings_text = result["findings"][0]
    # The successful search result should be present
    assert "Connection reset" in findings_text
    # The failed search should have an error entry
    assert "Error" in findings_text
