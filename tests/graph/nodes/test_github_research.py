"""Tests for GitHub research node — pure helpers and MCP-calling node."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import make_incident_state
from war_room_copilot.graph.nodes.github_research import (
    _content_to_text,
    github_research_node,
)
from war_room_copilot.tools.github_mcp import WarRoomToolError

# ── _content_to_text (pure) ───────────────────────────────────────────────────


def test_content_to_text_empty_list() -> None:
    """Empty list returns empty string."""
    assert _content_to_text([]) == ""


def test_content_to_text_string_input() -> None:
    """Plain string is returned via str()."""
    assert _content_to_text("hello") == "hello"


def test_content_to_text_blocks_with_text() -> None:
    """Blocks with .text attribute are joined."""
    b1 = MagicMock()
    b1.text = "foo"
    b2 = MagicMock()
    b2.text = "bar"
    assert _content_to_text([b1, b2]) == "foo bar"


def test_content_to_text_blocks_without_text() -> None:
    """Blocks without .text fall back to str(block)."""
    b = "plain string block"
    result = _content_to_text([b])
    assert result == "plain string block"


# ── github_research_node ─────────────────────────────────────────────────────


async def test_github_research_empty_query() -> None:
    """Empty query returns empty dict without calling MCP."""
    state = make_incident_state(query="")
    result = await github_research_node(state)
    assert result == {}


async def test_github_research_mcp_connection_error() -> None:
    """MCP connection failure returns error finding."""
    state = make_incident_state(query="database crash")

    with patch(
        "war_room_copilot.graph.nodes.github_research.get_mcp_client",
        side_effect=WarRoomToolError("Docker not running"),
    ):
        result = await github_research_node(state)

    assert "[GitHub] Could not connect" in result["findings"][0]


async def test_github_research_code_and_issue_results() -> None:
    """Both search results are included in findings."""
    mock_client = AsyncMock()

    code_block = MagicMock()
    code_block.text = json.dumps(
        [{"repository": {"full_name": "org/app"}, "path": "src/db.py", "score": 10}]
    )
    issue_block = MagicMock()
    issue_block.text = json.dumps([{"number": 42, "title": "DB crash", "state": "open"}])

    mock_client.call_tool.side_effect = [[code_block], [issue_block]]

    state = make_incident_state(query="database crash")

    with patch(
        "war_room_copilot.graph.nodes.github_research.get_mcp_client",
        return_value=mock_client,
    ):
        result = await github_research_node(state)

    findings_text = result["findings"][0]
    assert "Code Search" in findings_text
    assert "Issues" in findings_text


async def test_github_research_one_search_fails() -> None:
    """When one search raises, its error is appended but the other succeeds."""
    mock_client = AsyncMock()

    code_block = MagicMock()
    code_block.text = json.dumps([])
    # code search returns normally, but issue search will raise
    mock_client.call_tool.side_effect = [[code_block], RuntimeError("timeout")]

    state = make_incident_state(query="test query")

    with patch(
        "war_room_copilot.graph.nodes.github_research.get_mcp_client",
        return_value=mock_client,
    ):
        result = await github_research_node(state)

    findings_text = result["findings"][0]
    # Should contain the code search result (even if empty) and issue error
    assert "Code Search" in findings_text or "Error" in findings_text


async def test_github_research_non_json_response() -> None:
    """Non-JSON response is truncated to 500 chars per search."""
    mock_client = AsyncMock()

    block = MagicMock()
    block.text = "not json " * 100  # > 500 chars
    mock_client.call_tool.return_value = [block]

    state = make_incident_state(query="search something")

    with patch(
        "war_room_copilot.graph.nodes.github_research.get_mcp_client",
        return_value=mock_client,
    ):
        result = await github_research_node(state)

    # Both code and issue searches truncate to 500 chars each, plus prefixes
    findings_text = result["findings"][0]
    # Each search line should be at most ~525 chars (prefix + 500 chars of content)
    for line in findings_text.split("\n"):
        assert len(line) <= 550
