"""Async MCP client for the GitHub MCP server over streamable HTTP."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Tool

from war_room_copilot.config import get_settings
from war_room_copilot.models import FunctionSchema, ToolSchema

logger = logging.getLogger("war-room-copilot.tools.github_mcp")


# ── Errors ─────────────────────────────────────────────────────────────────────


class WarRoomToolError(Exception):
    """Base for all tool-layer errors."""


class MCPConnectionError(WarRoomToolError):
    """MCP server unreachable or failed to respond within timeout."""


class MCPServerError(WarRoomToolError):
    """MCP server crashed or returned a protocol-level error."""


class GitHubRateLimitError(WarRoomToolError):
    """GitHub API rate limit reached."""


# ── Schema conversion ──────────────────────────────────────────────────────────


def mcp_tool_to_schema(tool: Tool) -> ToolSchema:
    """Convert an MCP Tool to a function-calling schema.

    MCP uses JSON Schema for inputSchema; LLM providers use the same
    format under function.parameters — direct mapping, no transformation needed.
    """
    return ToolSchema(
        type="function",
        function=FunctionSchema(
            name=tool.name,
            description=tool.description or "",
            parameters=tool.inputSchema
            if tool.inputSchema is not None
            else {"type": "object", "properties": {}},
        ),
    )


# ── Client ─────────────────────────────────────────────────────────────────────


class GitHubMCPClient:
    """Async client for the GitHub MCP server over streamable HTTP.

    In Docker Compose, the MCP server runs as a sidecar service and the agent
    connects via HTTP (no Docker socket or CLI needed).

    For local development without Docker Compose, set GITHUB_MCP_URL to a
    locally-running instance (e.g. ``http://localhost:8090/mcp``).

    Usage (context manager — preferred for scripts/tests):

        async with GitHubMCPClient() as client:
            tools = client.tool_schemas()
            result = await client.call_tool("list_issues", {"owner": "...", "repo": "..."})

    Usage (long-lived — used by the LiveKit agent):

        client = GitHubMCPClient()
        await client.connect()
        ...
        await client.close()
    """

    def __init__(self, github_token: str | None = None) -> None:
        cfg = get_settings()
        self._token: str = github_token or cfg.github_token
        self._url: str = cfg.github_mcp_url
        self._tool_timeout: float = cfg.github_mcp_timeout
        self._connect_timeout: float = cfg.github_mcp_connect_timeout

        self._exit_stack: AsyncExitStack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tools: list[Tool] = []

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Connect to the GitHub MCP server over streamable HTTP.

        Raises MCPConnectionError if the server is unreachable or times out.
        """
        if self._session is not None:
            raise MCPConnectionError("Already connected. Call close() before reconnecting.")

        if not self._token:
            raise MCPConnectionError(
                "No GitHub token configured. Set GITHUB_TOKEN in your environment or .env file."
            )

        if not self._url:
            raise MCPConnectionError(
                "No GitHub MCP URL configured. Set GITHUB_MCP_URL or run via docker compose."
            )

        try:
            transport = await asyncio.wait_for(
                self._exit_stack.enter_async_context(
                    streamablehttp_client(
                        url=self._url,
                        headers={"Authorization": f"Bearer {self._token}"},
                        timeout=self._connect_timeout,
                    )
                ),
                timeout=self._connect_timeout,
            )
            read_stream, write_stream, _get_session_id = transport
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await self._session.initialize()

            response = await self._session.list_tools()
            self._tools = list(response.tools)
            logger.info(
                "GitHub MCP server ready at %s. %d tools available.",
                self._url,
                len(self._tools),
            )
        except MCPConnectionError:
            await self._exit_stack.aclose()
            self._session = None
            raise
        except asyncio.TimeoutError as exc:
            await self._exit_stack.aclose()
            self._session = None
            raise MCPConnectionError(
                f"GitHub MCP server at {self._url} did not respond within {self._connect_timeout}s."
            ) from exc
        except Exception as exc:
            await self._exit_stack.aclose()
            self._session = None
            raise MCPConnectionError(
                f"Failed to connect to GitHub MCP server at {self._url}: {exc}"
            ) from exc

    async def close(self) -> None:
        """Tear down the MCP session."""
        await self._exit_stack.aclose()
        self._session = None
        self._tools = []

    async def __aenter__(self) -> GitHubMCPClient:
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ── Tool introspection ─────────────────────────────────────────────────────

    def tool_schemas(self) -> list[dict[str, Any]]:
        """Return all MCP tools as function-calling schema dicts."""
        self._assert_connected()
        return [mcp_tool_to_schema(t).model_dump() for t in self._tools]

    def tool_names(self) -> list[str]:
        """Return the names of all available tools."""
        self._assert_connected()
        return [t.name for t in self._tools]

    # ── Tool execution ─────────────────────────────────────────────────────────

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Invoke a GitHub MCP tool by name.

        Returns the raw content from the MCP response (list of content blocks).

        Raises:
            MCPServerError: Protocol error or server crash.
            GitHubRateLimitError: GitHub API rate limit detected.
        """
        self._assert_connected()
        assert self._session is not None  # type narrowing for mypy

        try:
            result = await asyncio.wait_for(
                self._session.call_tool(name, arguments),
                timeout=self._tool_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise MCPServerError(f"Tool '{name}' timed out after {self._tool_timeout}s") from exc
        except Exception as exc:
            raise MCPServerError(f"Tool '{name}' failed: {exc}") from exc

        if result.isError:
            content_text = _extract_text(result.content)
            if "rate limit" in content_text.lower():
                raise GitHubRateLimitError(content_text)
            raise MCPServerError(f"Tool '{name}' returned error: {content_text}")

        return result.content

    # ── Internal ───────────────────────────────────────────────────────────────

    def _assert_connected(self) -> None:
        if self._session is None:
            raise MCPConnectionError(
                "GitHubMCPClient is not connected. "
                "Use 'async with GitHubMCPClient()' or call 'await client.connect()' first."
            )


def _extract_text(content: Any) -> str:
    """Best-effort text extraction from MCP content blocks."""
    if isinstance(content, list):
        return " ".join(block.text if hasattr(block, "text") else str(block) for block in content)
    return str(content)
