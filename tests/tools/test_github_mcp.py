"""Tests for the GitHub MCP client and schema conversion."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from war_room_copilot.models import OpenAITool
from war_room_copilot.tools.github_mcp import (
    GitHubMCPClient,
    GitHubRateLimitError,
    MCPConnectionError,
    MCPServerError,
    mcp_tool_to_openai,
)

# ── Schema conversion (pure, no I/O) ──────────────────────────────────────────


def _make_mock_tool(
    name: str = "list_issues",
    description: str = "List issues in a repository",
    input_schema: dict | None = None,
) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    tool.description = description
    tool.inputSchema = input_schema or {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
        },
        "required": ["owner", "repo"],
    }
    return tool


def test_mcp_tool_to_openai_basic() -> None:
    """Maps name, description, and inputSchema correctly."""
    result = mcp_tool_to_openai(_make_mock_tool())

    assert isinstance(result, OpenAITool)
    assert result.type == "function"
    assert result.function.name == "list_issues"
    assert result.function.description == "List issues in a repository"
    assert result.function.parameters["type"] == "object"
    assert "owner" in result.function.parameters["properties"]


def test_mcp_tool_to_openai_empty_schema() -> None:
    """Tools without inputSchema get an empty-object schema."""
    tool = _make_mock_tool(name="ping", description="Ping", input_schema=None)
    tool.inputSchema = None

    result = mcp_tool_to_openai(tool)
    assert result.function.parameters == {"type": "object", "properties": {}}


def test_openai_tools_serializable() -> None:
    """model_dump() output must be JSON-serializable."""
    dumped = mcp_tool_to_openai(_make_mock_tool()).model_dump()
    json.dumps(dumped)  # should not raise


# ── Error states ───────────────────────────────────────────────────────────────


def test_assert_connected_raises_before_connect() -> None:
    client = GitHubMCPClient(github_token="fake")
    with pytest.raises(MCPConnectionError, match="not connected"):
        client.openai_tools()


def test_tool_names_raises_before_connect() -> None:
    client = GitHubMCPClient(github_token="fake")
    with pytest.raises(MCPConnectionError, match="not connected"):
        client.tool_names()


async def test_call_tool_raises_on_mcp_error() -> None:
    client = GitHubMCPClient(github_token="fake")
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.isError = True
    mock_result.content = [MagicMock(text="Tool execution failed")]
    mock_session.call_tool.return_value = mock_result
    client._session = mock_session
    client._tools = []

    with pytest.raises(MCPServerError, match="Tool execution failed"):
        await client.call_tool("list_issues", {"owner": "foo", "repo": "bar"})


async def test_call_tool_rate_limit_raises_specific_error() -> None:
    client = GitHubMCPClient(github_token="fake")
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.isError = True
    mock_result.content = [MagicMock(text="API rate limit exceeded for token")]
    mock_session.call_tool.return_value = mock_result
    client._session = mock_session
    client._tools = []

    with pytest.raises(GitHubRateLimitError, match="rate limit"):
        await client.call_tool("list_issues", {"owner": "foo", "repo": "bar"})


async def test_call_tool_success_returns_content() -> None:
    client = GitHubMCPClient(github_token="fake")
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.isError = False
    mock_result.content = [MagicMock(text='[{"number": 1, "title": "Bug"}]')]
    mock_session.call_tool.return_value = mock_result
    client._session = mock_session
    client._tools = []

    result = await client.call_tool("list_issues", {"owner": "foo", "repo": "bar"})
    assert len(result) == 1
    assert hasattr(result[0], "text")


# ── openai_tools() with mocked tools ──────────────────────────────────────────


def test_openai_tools_converts_all() -> None:
    client = GitHubMCPClient(github_token="fake")
    client._session = MagicMock()  # pretend connected
    client._tools = [_make_mock_tool("t1", "Tool 1"), _make_mock_tool("t2", "Tool 2")]

    tools = client.openai_tools()
    assert len(tools) == 2
    assert tools[0]["function"]["name"] == "t1"
    assert tools[1]["function"]["name"] == "t2"
    assert all(t["type"] == "function" for t in tools)


# ── Integration test (requires Docker + GITHUB_TOKEN) ─────────────────────────


@pytest.mark.skipif(
    not os.getenv("GITHUB_TOKEN"),
    reason="GITHUB_TOKEN not set — skipping live Docker integration test",
)
async def test_connect_and_list_tools_live() -> None:
    async with GitHubMCPClient() as client:
        tools = client.tool_names()
        assert len(tools) > 0
        # Verify at least some expected tools exist
        assert any("issue" in t for t in tools)
        openai_tools = client.openai_tools()
        assert all(t["type"] == "function" for t in openai_tools)
