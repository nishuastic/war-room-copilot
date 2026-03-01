"""Async MCP client for the PagerDuty MCP server over streamable HTTP."""

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

logger = logging.getLogger("war-room-copilot.tools.pagerduty_mcp")


# ── Errors ─────────────────────────────────────────────────────────────────────


class PagerDutyRateLimitError(WarRoomToolError):
    """PagerDuty API rate limit reached."""


# ── Schema conversion ──────────────────────────────────────────────────────────


def mcp_tool_to_schema(tool: Tool) -> ToolSchema:
    """Convert an MCP Tool to a function-calling schema.

    MCP uses JSON Schema for inputSchema; LLM providers use the same
    format under function.parameters -- direct mapping, no transformation needed.
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


class PagerDutyMCPClient:
    """Async client for the PagerDuty MCP server over streamable HTTP.

    In Docker Compose, the MCP server runs as a sidecar service and the agent
    connects via HTTP (no Docker socket or CLI needed).

    For local development without Docker Compose, set PAGERDUTY_MCP_URL to a
    locally-running instance (e.g. ``http://localhost:8091/mcp``).

    Usage (context manager -- preferred for scripts/tests):

        async with PagerDutyMCPClient() as client:
            tools = client.tool_schemas()
            result = await client.call_tool(
                "list_incidents", {"statuses": ["triggered", "acknowledged"]}
            )

    Usage (long-lived -- used by the LiveKit agent):

        client = PagerDutyMCPClient()
        await client.connect()
        ...
        await client.close()
    """

    def __init__(self, api_key: str | None = None) -> None:
        cfg = get_settings()
        self._token: str = api_key or cfg.pagerduty_api_key
        self._url: str = cfg.pagerduty_mcp_url
        self._tool_timeout: float = cfg.pagerduty_mcp_timeout
        self._connect_timeout: float = cfg.pagerduty_mcp_connect_timeout

        self._exit_stack: AsyncExitStack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tools: list[Tool] = []

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Connect to the PagerDuty MCP server over streamable HTTP.

        Raises MCPConnectionError if the server is unreachable or times out.
        """
        if self._session is not None:
            raise MCPConnectionError("Already connected. Call close() before reconnecting.")

        if not self._token:
            raise MCPConnectionError(
                "No PagerDuty API key configured. "
                "Set PAGERDUTY_API_KEY in your environment or .env file."
            )

        if not self._url:
            raise MCPConnectionError(
                "No PagerDuty MCP URL configured. Set PAGERDUTY_MCP_URL or run via docker compose."
            )

        try:
            transport = await asyncio.wait_for(
                self._exit_stack.enter_async_context(
                    streamablehttp_client(
                        url=self._url,
                        headers={"Authorization": f"Token token={self._token}"},
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
                "PagerDuty MCP server ready at %s. %d tools available.",
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
                "PagerDuty MCP server at %s did not respond "
                "within %ss." % (self._url, self._connect_timeout)
            ) from exc
        except Exception as exc:
            await self._exit_stack.aclose()
            self._session = None
            raise MCPConnectionError(
                "Failed to connect to PagerDuty MCP server at %s: %s" % (self._url, exc)
            ) from exc

    async def close(self) -> None:
        """Tear down the MCP session."""
        await self._exit_stack.aclose()
        self._session = None
        self._tools = []

    async def __aenter__(self) -> PagerDutyMCPClient:
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
        """Invoke a PagerDuty MCP tool by name.

        Returns the raw content from the MCP response (list of content blocks).

        Raises:
            MCPServerError: Protocol error or server crash.
            PagerDutyRateLimitError: PagerDuty API rate limit detected.
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
                raise PagerDutyRateLimitError(content_text)
            raise MCPServerError("Tool '%s' returned error: %s" % (name, content_text))

        return result.content

    # ── Internal ───────────────────────────────────────────────────────────────

    def _assert_connected(self) -> None:
        if self._session is None:
            raise MCPConnectionError(
                "PagerDutyMCPClient is not connected. "
                "Use 'async with PagerDutyMCPClient()' or "
                "call 'await client.connect()' first."
            )


# ── Helpers ────────────────────────────────────────────────────────────────────


def _extract_text(content: Any) -> str:
    """Best-effort text extraction from MCP content blocks."""
    if isinstance(content, list):
        return " ".join(block.text if hasattr(block, "text") else str(block) for block in content)
    return str(content)


def _parse_json_response(raw: Any) -> list[dict[str, Any]]:
    """Parse MCP content blocks into a list of dicts.

    Tolerant -- returns an empty list on failure rather than crashing.
    """
    if isinstance(raw, BaseException):
        logger.warning(
            "PagerDuty API call failed (%s): %s -- returning empty list",
            type(raw).__name__,
            raw,
        )
        return []
    try:
        text = _extract_text(raw)
        data = json.loads(text)
        if isinstance(data, dict):
            # PagerDuty responses often wrap arrays in a top-level key
            # e.g. {"incidents": [...]} or {"services": [...]}
            for key in ("incidents", "services", "oncalls", "users"):
                if key in data and isinstance(data[key], list):
                    return data[key]  # type: ignore[no-any-return]
            return [data]
        if isinstance(data, list):
            return data  # type: ignore[no-any-return]
        return [data]
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning(
            "Failed to parse PagerDuty response as JSON (%s): %s",
            type(exc).__name__,
            exc,
        )
        return []


# ── High-level helpers ─────────────────────────────────────────────────────────


async def get_pd_incidents(
    client: PagerDutyMCPClient,
    statuses: list[str] | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Fetch current PagerDuty incidents.

    Args:
        client: Connected PagerDutyMCPClient instance.
        statuses: Filter by status (e.g. ["triggered", "acknowledged"]).
            Defaults to triggered + acknowledged (active incidents).
        limit: Maximum number of incidents to return.

    Returns:
        List of incident dicts, or empty list on failure.
    """
    if statuses is None:
        statuses = ["triggered", "acknowledged"]

    raw = await asyncio.gather(
        client.call_tool(
            "list_incidents",
            {"statuses": statuses, "limit": limit},
        ),
        return_exceptions=True,
    )
    incidents = _parse_json_response(raw[0])

    if incidents:
        logger.info(
            "Fetched %d PagerDuty incidents (statuses=%s)",
            len(incidents),
            statuses,
        )
    else:
        logger.info("No PagerDuty incidents found (statuses=%s)", statuses)

    return incidents


async def get_pd_services(
    client: PagerDutyMCPClient,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Fetch PagerDuty services.

    Args:
        client: Connected PagerDutyMCPClient instance.
        limit: Maximum number of services to return.

    Returns:
        List of service dicts, or empty list on failure.
    """
    raw = await asyncio.gather(
        client.call_tool("list_services", {"limit": limit}),
        return_exceptions=True,
    )
    services = _parse_json_response(raw[0])

    logger.info("Fetched %d PagerDuty services", len(services))
    return services


async def get_pd_oncall(
    client: PagerDutyMCPClient,
    schedule_ids: list[str] | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Fetch current on-call schedules from PagerDuty.

    Args:
        client: Connected PagerDutyMCPClient instance.
        schedule_ids: Optional list of schedule IDs to filter by.
        limit: Maximum number of on-call entries to return.

    Returns:
        List of on-call dicts, or empty list on failure.
    """
    arguments: dict[str, Any] = {"limit": limit}
    if schedule_ids:
        arguments["schedule_ids"] = schedule_ids

    raw = await asyncio.gather(
        client.call_tool("list_oncalls", arguments),
        return_exceptions=True,
    )
    oncalls = _parse_json_response(raw[0])

    logger.info("Fetched %d PagerDuty on-call entries", len(oncalls))
    return oncalls


def format_incidents_for_llm(incidents: list[dict[str, Any]]) -> str:
    """Render PagerDuty incidents as compact text for LLM injection.

    Extracts the most useful fields from each incident dict and formats
    them into a concise, readable block.
    """
    if not incidents:
        return "PagerDuty Incidents: none active"

    lines = [f"PagerDuty Active Incidents ({len(incidents)}):"]
    for inc in incidents:
        inc_id = inc.get("incident_number", inc.get("id", "?"))
        title = inc.get("title", inc.get("summary", "Untitled"))
        status = inc.get("status", "unknown")
        urgency = inc.get("urgency", "unknown")
        service = ""
        svc_data = inc.get("service")
        if isinstance(svc_data, dict):
            service = svc_data.get("summary", "")
        created = inc.get("created_at", "")
        lines.append(
            f"  #{inc_id} [{status}/{urgency}] {title}"
            + (f" (service: {service})" if service else "")
            + (f" created: {created}" if created else "")
        )
    return "\n".join(lines)


def format_oncall_for_llm(oncalls: list[dict[str, Any]]) -> str:
    """Render PagerDuty on-call data as compact text for LLM injection."""
    if not oncalls:
        return "PagerDuty On-Call: no schedules found"

    lines = [f"PagerDuty On-Call ({len(oncalls)} entries):"]
    for entry in oncalls:
        user = entry.get("user", {})
        user_name = user.get("summary", user.get("name", "Unknown"))
        schedule = entry.get("schedule", {})
        sched_name = schedule.get("summary", "Unscheduled")
        escalation = entry.get("escalation_policy", {})
        esc_name = escalation.get("summary", "")
        level = entry.get("escalation_level", "?")
        lines.append(
            f"  L{level}: {user_name} -- {sched_name}"
            + (f" (policy: {esc_name})" if esc_name else "")
        )
    return "\n".join(lines)


def format_services_for_llm(services: list[dict[str, Any]]) -> str:
    """Render PagerDuty services as compact text for LLM injection."""
    if not services:
        return "PagerDuty Services: none found"

    lines = [f"PagerDuty Services ({len(services)}):"]
    for svc in services:
        name = svc.get("name", svc.get("summary", "Unnamed"))
        status = svc.get("status", "unknown")
        desc = svc.get("description", "")
        lines.append(f"  {name} [{status}]" + (f" -- {desc[:80]}" if desc else ""))
    return "\n".join(lines)
