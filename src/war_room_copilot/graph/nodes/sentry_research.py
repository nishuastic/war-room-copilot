"""Sentry research node — queries error tracking via the Sentry MCP client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.messages import AIMessage

from war_room_copilot.graph.state import IncidentState
from war_room_copilot.tools.github_mcp import WarRoomToolError
from war_room_copilot.tools.sentry_mcp import (
    SentryMCPClient,
    format_sentry_issues_for_llm,
    get_sentry_issues,
    search_sentry_errors,
)

logger = logging.getLogger("war-room-copilot.graph.nodes.sentry_research")

# Shared client instance — connected once, reused across invocations.
_sentry_client: SentryMCPClient | None = None


async def get_sentry_client() -> SentryMCPClient:
    """Return a connected Sentry MCP client, creating one if needed."""
    global _sentry_client  # noqa: PLW0603
    if _sentry_client is not None:
        try:
            _sentry_client.tool_names()
            return _sentry_client
        except Exception:
            logger.warning("Sentry MCP client connection lost, reconnecting...")
            try:
                await _sentry_client.close()
            except Exception:
                pass
            _sentry_client = None

    _sentry_client = SentryMCPClient()
    await _sentry_client.connect()
    return _sentry_client


async def close_sentry_client() -> None:
    """Tear down the shared Sentry MCP client."""
    global _sentry_client  # noqa: PLW0603
    if _sentry_client is not None:
        await _sentry_client.close()
        _sentry_client = None


async def sentry_research_node(state: IncidentState) -> dict[str, Any]:
    """Research Sentry for error context relevant to the current query.

    Searches issues and recent errors in parallel, then combines results
    into a findings string.
    """
    query = state.get("query", "")
    if not query:
        return {}

    try:
        client = await get_sentry_client()
    except WarRoomToolError as exc:
        logger.warning("Sentry MCP unavailable: %s", exc)
        finding = f"[Sentry] Could not connect to Sentry: {exc}"
        return {
            "findings": [finding],
            "messages": [AIMessage(content=finding)],
        }

    # Run issue search and error search in parallel
    issues_result, search_result = await asyncio.gather(
        _safe_get_issues(client),
        _safe_search_errors(client, query),
        return_exceptions=True,
    )

    findings: list[str] = []

    if isinstance(issues_result, str):
        findings.append(issues_result)
    elif isinstance(issues_result, Exception):
        logger.warning("Sentry issue fetch failed: %s", issues_result)
        findings.append(f"[Sentry Issues] Error: {issues_result}")

    if isinstance(search_result, str):
        findings.append(search_result)
    elif isinstance(search_result, Exception):
        logger.warning("Sentry error search failed: %s", search_result)
        findings.append(f"[Sentry Search] Error: {search_result}")

    summary = "\n".join(findings) if findings else "[Sentry] No results found."
    return {
        "findings": [summary],
        "messages": [AIMessage(content=summary)],
    }


async def _safe_get_issues(client: SentryMCPClient) -> str:
    """Fetch recent unresolved Sentry issues, returning formatted text."""
    issues = await get_sentry_issues(client)
    return format_sentry_issues_for_llm(issues)


async def _safe_search_errors(client: SentryMCPClient, query: str) -> str:
    """Search Sentry errors matching the query, returning formatted text."""
    results = await search_sentry_errors(client, query)
    return format_sentry_issues_for_llm(results)
