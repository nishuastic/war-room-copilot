"""Async MCP client for the GitHub MCP server running in Docker over stdio."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool

from war_room_copilot.config import get_settings
from war_room_copilot.models import OpenAIFunction, OpenAITool

logger = logging.getLogger("war-room-copilot.tools.github_mcp")


# ── Errors ─────────────────────────────────────────────────────────────────────


class WarRoomToolError(Exception):
    """Base for all tool-layer errors."""


class MCPConnectionError(WarRoomToolError):
    """Docker not available, or server failed to start within timeout."""


class MCPServerError(WarRoomToolError):
    """MCP server crashed or returned a protocol-level error."""


class GitHubRateLimitError(WarRoomToolError):
    """GitHub API rate limit reached."""


# ── Schema conversion ──────────────────────────────────────────────────────────


def mcp_tool_to_openai(tool: Tool) -> OpenAITool:
    """Convert an MCP Tool to an OpenAI function-calling schema.

    MCP uses JSON Schema for inputSchema; OpenAI uses the same format
    under function.parameters — direct mapping, no transformation needed.
    """
    return OpenAITool(
        type="function",
        function=OpenAIFunction(
            name=tool.name,
            description=tool.description or "",
            parameters=tool.inputSchema
            if tool.inputSchema is not None
            else {"type": "object", "properties": {}},
        ),
    )


# ── Client ─────────────────────────────────────────────────────────────────────


class GitHubMCPClient:
    """Async client for the GitHub MCP server running in Docker over stdio.

    Usage (context manager — preferred for scripts/tests):

        async with GitHubMCPClient() as client:
            tools = client.openai_tools()
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
        self._image: str = cfg.github_mcp_image
        self._tool_timeout: float = cfg.github_mcp_timeout
        self._connect_timeout: float = cfg.github_mcp_connect_timeout

        self._exit_stack: AsyncExitStack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tools: list[Tool] = []

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Start Docker container and establish MCP session.

        Raises MCPConnectionError if Docker is unavailable or startup times out.
        """
        if self._session is not None:
            raise MCPConnectionError("Already connected. Call close() before reconnecting.")

        if not self._token:
            raise MCPConnectionError(
                "No GitHub token configured. Set GITHUB_TOKEN in your environment or .env file."
            )

        server_params = StdioServerParameters(
            command="docker",
            args=[
                "run",
                "--rm",
                "-i",
                "-e",
                "GITHUB_PERSONAL_ACCESS_TOKEN",
                self._image,
            ],
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": self._token},
        )

        try:
            transport = await asyncio.wait_for(
                self._exit_stack.enter_async_context(stdio_client(server_params)),
                timeout=self._connect_timeout,
            )
            read_stream, write_stream = transport
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await self._session.initialize()

            response = await self._session.list_tools()
            self._tools = list(response.tools)
            logger.info(
                "GitHub MCP server ready. %d tools available.",
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
                f"GitHub MCP server ({self._image}) did not start "
                f"within {self._connect_timeout}s. Is Docker running?"
            ) from exc
        except Exception as exc:
            await self._exit_stack.aclose()
            self._session = None
            raise MCPConnectionError(f"Failed to start GitHub MCP server: {exc}") from exc

    async def close(self) -> None:
        """Tear down the MCP session and Docker subprocess."""
        await self._exit_stack.aclose()
        self._session = None
        self._tools = []

    async def __aenter__(self) -> GitHubMCPClient:
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ── Tool introspection ─────────────────────────────────────────────────────

    def openai_tools(self) -> list[dict[str, Any]]:
        """Return all MCP tools as OpenAI function-calling dicts.

        Ready to pass directly to ``openai.chat.completions.create(tools=...)``.
        """
        self._assert_connected()
        return [mcp_tool_to_openai(t).model_dump() for t in self._tools]

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
