"""GitHub research node — queries repos via the existing MCP client."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import AIMessage

from war_room_copilot.config import get_settings
from war_room_copilot.graph.state import IncidentState
from war_room_copilot.tools.github_mcp import GitHubMCPClient, WarRoomToolError

logger = logging.getLogger("war-room-copilot.graph.nodes.github_research")

# Shared client instance — connected once, reused across invocations.
_mcp_client: GitHubMCPClient | None = None


async def get_mcp_client() -> GitHubMCPClient:
    """Return a connected MCP client, creating one if needed.

    If the existing connection is broken, resets and creates a new one.
    """
    global _mcp_client  # noqa: PLW0603
    if _mcp_client is not None:
        try:
            # Lightweight health check — list tool names to verify connection
            _mcp_client.tool_names()
            return _mcp_client
        except Exception:
            logger.warning("MCP client connection lost, reconnecting...")
            try:
                await _mcp_client.close()
            except Exception:
                pass
            _mcp_client = None

    _mcp_client = GitHubMCPClient()
    await _mcp_client.connect()
    return _mcp_client


async def close_mcp_client() -> None:
    """Tear down the shared MCP client."""
    global _mcp_client  # noqa: PLW0603
    if _mcp_client is not None:
        await _mcp_client.close()
        _mcp_client = None


def _content_to_text(content: Any) -> str:
    """Extract text from MCP content blocks."""
    if isinstance(content, list):
        return " ".join(block.text if hasattr(block, "text") else str(block) for block in content)
    return str(content)


async def _search_code(client: GitHubMCPClient, query: str) -> str:
    """Search code via MCP, returning a formatted findings string."""
    cfg = get_settings()
    owner = cfg.default_repo_owner
    repo = cfg.default_repo_name

    params: dict[str, Any] = {"q": query}
    if owner and repo:
        params = {"owner": owner, "repo": repo, "query": query}

    code_results = await client.call_tool("search_code", params)
    code_text = _content_to_text(code_results)
    try:
        items = json.loads(code_text)
        if isinstance(items, dict) and "items" in items:
            items = items["items"]
        if isinstance(items, list):
            hits = [
                f"  - {it.get('repository', {}).get('full_name', '?')}:"
                f" {it.get('path', '?')} (score {it.get('score', '?')})"
                for it in items[:5]
            ]
            return f"[GitHub Code Search] {len(items)} results:\n" + "\n".join(hits)
        return f"[GitHub Code Search] {code_text[:500]}"
    except (json.JSONDecodeError, TypeError):
        return f"[GitHub Code Search] {code_text[:500]}"


async def _search_issues(client: GitHubMCPClient, query: str) -> str:
    """Search issues via MCP, returning a formatted findings string."""
    cfg = get_settings()
    owner = cfg.default_repo_owner
    repo = cfg.default_repo_name

    params: dict[str, Any] = {"q": query}
    if owner and repo:
        params = {"owner": owner, "repo": repo, "query": query}

    issue_results = await client.call_tool("search_issues", params)
    issue_text = _content_to_text(issue_results)
    try:
        items = json.loads(issue_text)
        if isinstance(items, dict) and "items" in items:
            items = items["items"]
        if isinstance(items, list):
            hits = [
                f"  - #{it.get('number', '?')} {it.get('title', '?')} [{it.get('state', '?')}]"
                for it in items[:5]
            ]
            return f"[GitHub Issues] {len(items)} results:\n" + "\n".join(hits)
        return f"[GitHub Issues] {issue_text[:500]}"
    except (json.JSONDecodeError, TypeError):
        return f"[GitHub Issues] {issue_text[:500]}"


async def github_research_node(state: IncidentState) -> dict[str, Any]:
    """Research GitHub for context relevant to the current query.

    Calls search_code and search_issues in parallel, then appends a
    formatted summary to ``findings``.
    """
    query = state.get("query", "")
    if not query:
        return {}

    try:
        client = await get_mcp_client()
    except WarRoomToolError as exc:
        logger.warning("GitHub MCP unavailable: %s", exc)
        finding = f"[GitHub] Could not connect to GitHub: {exc}"
        return {
            "findings": [finding],
            "messages": [AIMessage(content=finding)],
        }

    # Run code and issue searches in parallel
    findings: list[str] = []
    code_result, issue_result = await asyncio.gather(
        _search_code(client, query),
        _search_issues(client, query),
        return_exceptions=True,
    )

    if isinstance(code_result, str):
        findings.append(code_result)
    elif isinstance(code_result, Exception):
        logger.warning("Code search failed: %s", code_result)
        findings.append(f"[GitHub Code Search] Error: {code_result}")

    if isinstance(issue_result, str):
        findings.append(issue_result)
    elif isinstance(issue_result, Exception):
        logger.warning("Issue search failed: %s", issue_result)
        findings.append(f"[GitHub Issues] Error: {issue_result}")

    summary = "\n".join(findings) if findings else "[GitHub] No results found."
    return {
        "findings": [summary],
        "messages": [AIMessage(content=summary)],
    }
