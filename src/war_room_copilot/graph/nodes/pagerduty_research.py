"""PagerDuty research node — queries incidents and on-call via the PagerDuty MCP client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.messages import AIMessage

from war_room_copilot.graph.state import IncidentState
from war_room_copilot.tools.github_mcp import WarRoomToolError
from war_room_copilot.tools.pagerduty_mcp import (
    PagerDutyMCPClient,
    format_incidents_for_llm,
    format_oncall_for_llm,
    get_pd_incidents,
    get_pd_oncall,
)

logger = logging.getLogger("war-room-copilot.graph.nodes.pagerduty_research")

# Shared client instance — connected once, reused across invocations.
_pd_client: PagerDutyMCPClient | None = None


async def get_pd_client() -> PagerDutyMCPClient:
    """Return a connected PagerDuty MCP client, creating one if needed."""
    global _pd_client  # noqa: PLW0603
    if _pd_client is not None:
        try:
            _pd_client.tool_names()
            return _pd_client
        except Exception:
            logger.warning("PagerDuty MCP client connection lost, reconnecting...")
            try:
                await _pd_client.close()
            except Exception:
                pass
            _pd_client = None

    _pd_client = PagerDutyMCPClient()
    await _pd_client.connect()
    return _pd_client


async def close_pd_client() -> None:
    """Tear down the shared PagerDuty MCP client."""
    global _pd_client  # noqa: PLW0603
    if _pd_client is not None:
        await _pd_client.close()
        _pd_client = None


async def pagerduty_research_node(state: IncidentState) -> dict[str, Any]:
    """Research PagerDuty for incident context relevant to the current query.

    Fetches active incidents and on-call schedules in parallel, then
    combines results into a findings string.
    """
    query = state.get("query", "")
    if not query:
        return {}

    try:
        client = await get_pd_client()
    except WarRoomToolError as exc:
        logger.warning("PagerDuty MCP unavailable: %s", exc)
        finding = f"[PagerDuty] Could not connect to PagerDuty: {exc}"
        return {
            "findings": [finding],
            "messages": [AIMessage(content=finding)],
        }

    # Run incident fetch and on-call lookup in parallel
    incidents_result, oncall_result = await asyncio.gather(
        _safe_get_incidents(client),
        _safe_get_oncall(client),
        return_exceptions=True,
    )

    findings: list[str] = []

    if isinstance(incidents_result, str):
        findings.append(incidents_result)
    elif isinstance(incidents_result, Exception):
        logger.warning("PagerDuty incident fetch failed: %s", incidents_result)
        findings.append(f"[PagerDuty Incidents] Error: {incidents_result}")

    if isinstance(oncall_result, str):
        findings.append(oncall_result)
    elif isinstance(oncall_result, Exception):
        logger.warning("PagerDuty on-call fetch failed: %s", oncall_result)
        findings.append(f"[PagerDuty On-Call] Error: {oncall_result}")

    summary = "\n".join(findings) if findings else "[PagerDuty] No results found."
    return {
        "findings": [summary],
        "messages": [AIMessage(content=summary)],
    }


async def _safe_get_incidents(client: PagerDutyMCPClient) -> str:
    """Fetch active PagerDuty incidents, returning formatted text."""
    incidents = await get_pd_incidents(client)
    return format_incidents_for_llm(incidents)


async def _safe_get_oncall(client: PagerDutyMCPClient) -> str:
    """Fetch on-call schedules, returning formatted text."""
    oncalls = await get_pd_oncall(client)
    return format_oncall_for_llm(oncalls)
