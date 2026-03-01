"""Async MCP client for the Sentry MCP server over streamable HTTP."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Tool

from war_room_copilot.config import get_settings
from war_room_copilot.models import FunctionSchema, ToolSchema
from war_room_copilot.tools.github_mcp import (
    MCPConnectionError,
    MCPServerError,
    WarRoomToolError,
)

logger = logging.getLogger("war-room-copilot.tools.sentry_mcp")


# ── Errors ─────────────────────────────────────────────────────────────────────


class SentryRateLimitError(WarRoomToolError):
    """Sentry API rate limit reached."""


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


class SentryMCPClient:
    """Async client for the Sentry MCP server over streamable HTTP.

    In Docker Compose, the MCP server runs as a sidecar service and the agent
    connects via HTTP (no Docker socket or CLI needed).

    For local development without Docker Compose, set SENTRY_MCP_URL to a
    locally-running instance (e.g. ``http://localhost:8092/mcp``).

    Usage (context manager — preferred for scripts/tests):

        async with SentryMCPClient() as client:
            tools = client.tool_schemas()
            result = await client.call_tool("list_issues", {"org": "...", "project": "..."})

    Usage (long-lived — used by the LiveKit agent):

        client = SentryMCPClient()
        await client.connect()
        ...
        await client.close()
    """

    def __init__(self, sentry_auth_token: str | None = None) -> None:
        cfg = get_settings()
        self._token: str = sentry_auth_token or cfg.sentry_auth_token
        self._url: str = cfg.sentry_mcp_url
        self._tool_timeout: float = cfg.sentry_mcp_timeout
        self._connect_timeout: float = cfg.sentry_mcp_connect_timeout

        self._exit_stack: AsyncExitStack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tools: list[Tool] = []

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Connect to the Sentry MCP server over streamable HTTP.

        Raises MCPConnectionError if the server is unreachable or times out.
        """
        if self._session is not None:
            raise MCPConnectionError("Already connected. Call close() before reconnecting.")

        if not self._token:
            raise MCPConnectionError(
                "No Sentry auth token configured. "
                "Set SENTRY_AUTH_TOKEN in your environment or .env file."
            )

        if not self._url:
            raise MCPConnectionError(
                "No Sentry MCP URL configured. Set SENTRY_MCP_URL or run via docker compose."
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
                "Sentry MCP server ready at %s. %d tools available.",
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
                "Sentry MCP server at %s did not respond within %ss."
                % (self._url, self._connect_timeout)
            ) from exc
        except Exception as exc:
            await self._exit_stack.aclose()
            self._session = None
            raise MCPConnectionError(
                "Failed to connect to Sentry MCP server at %s: %s" % (self._url, exc)
            ) from exc

    async def close(self) -> None:
        """Tear down the MCP session."""
        await self._exit_stack.aclose()
        self._session = None
        self._tools = []

    async def __aenter__(self) -> SentryMCPClient:
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
        """Invoke a Sentry MCP tool by name.

        Returns the raw content from the MCP response (list of content blocks).

        Raises:
            MCPServerError: Protocol error or server crash.
            SentryRateLimitError: Sentry API rate limit detected.
        """
        self._assert_connected()
        assert self._session is not None  # type narrowing for mypy

        try:
            result = await asyncio.wait_for(
                self._session.call_tool(name, arguments),
                timeout=self._tool_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise MCPServerError(
                "Tool '%s' timed out after %ss" % (name, self._tool_timeout)
            ) from exc
        except Exception as exc:
            raise MCPServerError("Tool '%s' failed: %s" % (name, exc)) from exc

        if result.isError:
            content_text = _extract_text(result.content)
            if "rate limit" in content_text.lower():
                raise SentryRateLimitError(content_text)
            raise MCPServerError("Tool '%s' returned error: %s" % (name, content_text))

        return result.content

    # ── Internal ───────────────────────────────────────────────────────────────

    def _assert_connected(self) -> None:
        if self._session is None:
            raise MCPConnectionError(
                "SentryMCPClient is not connected. "
                "Use 'async with SentryMCPClient()' or call "
                "'await client.connect()' first."
            )


# ── Helpers ────────────────────────────────────────────────────────────────────


def _extract_text(content: Any) -> str:
    """Best-effort text extraction from MCP content blocks."""
    if isinstance(content, list):
        return " ".join(block.text if hasattr(block, "text") else str(block) for block in content)
    return str(content)


def _parse_json_response(raw: Any) -> list[dict[str, Any]]:
    """Parse MCP content blocks into a list of dicts.

    Returns an empty list on failure — partial results beat crashes.
    """
    if isinstance(raw, BaseException):
        logger.warning(
            "Sentry API call failed (%s): %s — returning empty list",
            type(raw).__name__,
            raw,
        )
        return []
    try:
        text = _extract_text(raw)
        data = json.loads(text)
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]
    except json.JSONDecodeError as exc:
        logger.warning(
            "Failed to parse Sentry response as JSON (%s): %s",
            type(exc).__name__,
            exc,
        )
        return []
    except Exception as exc:
        logger.error(
            "Failed to parse Sentry tool response (%s): %s",
            type(exc).__name__,
            exc,
        )
        return []


# ── High-level facades ─────────────────────────────────────────────────────────


async def get_sentry_issues(
    client: SentryMCPClient,
    org: str | None = None,
    project: str | None = None,
    query: str | None = None,
    max_results: int = 25,
) -> list[dict[str, Any]]:
    """Fetch recent Sentry issues for a project.

    Uses the Sentry MCP ``list_issues`` tool to retrieve unresolved issues.
    Falls back to defaults from config if *org* / *project* are not provided.

    Returns a list of issue dicts, each containing at minimum:
    ``id``, ``title``, ``culprit``, ``level``, ``count``, ``firstSeen``,
    ``lastSeen``, ``permalink``.
    """
    cfg = get_settings()
    org = org or cfg.default_sentry_org
    project = project or cfg.default_sentry_project

    if not org or not project:
        raise ValueError(
            "org and project must be provided, or set DEFAULT_SENTRY_ORG "
            "and DEFAULT_SENTRY_PROJECT in your environment."
        )

    arguments: dict[str, Any] = {
        "organization_slug": org,
        "project_slug": project,
        "query": query or "is:unresolved",
        "limit": max_results,
    }

    raw = await client.call_tool("list_issues", arguments)
    issues = _parse_json_response(raw)

    logger.info(
        "Fetched %d Sentry issues for %s/%s",
        len(issues),
        org,
        project,
    )
    return issues


async def get_sentry_events(
    client: SentryMCPClient,
    issue_id: str,
    org: str | None = None,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Fetch recent events (occurrences) for a specific Sentry issue.

    Each event dict typically contains: ``eventID``, ``message``,
    ``timestamp``, ``tags``, ``context``, and ``entries`` (stack traces, etc.).
    """
    cfg = get_settings()
    org = org or cfg.default_sentry_org

    if not org:
        raise ValueError("org must be provided, or set DEFAULT_SENTRY_ORG in your environment.")

    arguments: dict[str, Any] = {
        "organization_slug": org,
        "issue_id": issue_id,
        "limit": max_results,
    }

    raw = await client.call_tool("list_issue_events", arguments)
    events = _parse_json_response(raw)

    logger.info(
        "Fetched %d events for Sentry issue %s",
        len(events),
        issue_id,
    )
    return events


async def search_sentry_errors(
    client: SentryMCPClient,
    query: str,
    org: str | None = None,
    project: str | None = None,
    max_results: int = 25,
) -> list[dict[str, Any]]:
    """Search Sentry issues matching a free-text query.

    Wraps the MCP ``search_issues`` tool. The *query* supports Sentry's
    search syntax (e.g. ``is:unresolved level:error message:timeout``).

    Returns a list of matching issue dicts.
    """
    cfg = get_settings()
    org = org or cfg.default_sentry_org
    project = project or cfg.default_sentry_project

    if not org:
        raise ValueError("org must be provided, or set DEFAULT_SENTRY_ORG in your environment.")

    arguments: dict[str, Any] = {
        "organization_slug": org,
        "query": query,
        "limit": max_results,
    }
    if project:
        arguments["project_slug"] = project

    raw = await client.call_tool("search_issues", arguments)
    results = _parse_json_response(raw)

    logger.info(
        "Sentry search for '%s' in %s returned %d results",
        query,
        org,
        len(results),
    )
    return results


def format_sentry_issues_for_llm(issues: list[dict[str, Any]]) -> str:
    """Format a list of Sentry issues into compact text for LLM consumption.

    Produces a token-efficient summary suitable for injecting into a prompt.
    """
    if not issues:
        return "Sentry Issues: none"

    lines = [f"Sentry Issues ({len(issues)}):"]
    for issue in issues:
        title = issue.get("title", "Unknown")
        level = issue.get("level", "unknown")
        count = issue.get("count", "?")
        culprit = issue.get("culprit", "")
        last_seen = issue.get("lastSeen", "")
        issue_id = issue.get("id", "")
        permalink = issue.get("permalink", "")

        line = f"  - [{level.upper()}] {title}"
        if culprit:
            line += f" in {culprit}"
        line += f" (count={count}"
        if last_seen:
            line += f", last={last_seen}"
        line += ")"
        if permalink:
            line += f" {permalink}"
        elif issue_id:
            line += f" [id={issue_id}]"
        lines.append(line)

    return "\n".join(lines)


def format_sentry_events_for_llm(
    events: list[dict[str, Any]],
    issue_title: str = "",
) -> str:
    """Format Sentry events into compact text for LLM consumption.

    Includes timestamps, messages, and abbreviated stack traces.
    """
    if not events:
        return "Sentry Events: none"

    header = f"Sentry Events for '{issue_title}'" if issue_title else "Sentry Events"
    lines = [f"{header} ({len(events)}):"]

    for event in events:
        event_id = event.get("eventID", "?")[:8]
        timestamp = event.get("timestamp", "")
        message = event.get("message", event.get("title", ""))

        line = f"  - [{event_id}] {timestamp}: {message}"

        # Extract first stack frame if available
        entries = event.get("entries", [])
        for entry in entries:
            if entry.get("type") == "exception":
                exc_data = entry.get("data", {})
                values = exc_data.get("values", [])
                if values:
                    exc_val = values[0]
                    exc_type = exc_val.get("type", "")
                    exc_value = exc_val.get("value", "")
                    if exc_type:
                        line += f" | {exc_type}: {exc_value}"
                    frames = exc_val.get("stacktrace", {}).get("frames", [])
                    if frames:
                        top = frames[-1]
                        filename = top.get("filename", "?")
                        lineno = top.get("lineNo", "?")
                        func = top.get("function", "?")
                        line += f" @ {filename}:{lineno} in {func}"
                break

        lines.append(line)

    return "\n".join(lines)
