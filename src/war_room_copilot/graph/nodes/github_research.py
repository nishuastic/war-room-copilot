"""GitHub research node — queries repos via the existing MCP client."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage

from war_room_copilot.graph.state import IncidentState
from war_room_copilot.tools.github_mcp import GitHubMCPClient, WarRoomToolError

logger = logging.getLogger("war-room-copilot.graph.nodes.github_research")

# Shared client instance — connected once, reused across invocations.
_mcp_client: GitHubMCPClient | None = None


async def get_mcp_client() -> GitHubMCPClient:
    """Return a connected MCP client, creating one if needed."""
    global _mcp_client  # noqa: PLW0603
    if _mcp_client is None:
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


async def github_research_node(state: IncidentState) -> dict[str, Any]:
    """Research GitHub for context relevant to the current query.

    Calls search_code and list_issues in parallel, then appends a
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
            "findings": state.get("findings", []) + [finding],
            "messages": [AIMessage(content=finding)],
        }

    findings: list[str] = []

    # Search code
    try:
        code_results = await client.call_tool("search_code", {"q": query})
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
                findings.append(f"[GitHub Code Search] {len(items)} results:\n" + "\n".join(hits))
            else:
                findings.append(f"[GitHub Code Search] {code_text[:500]}")
        except (json.JSONDecodeError, TypeError):
            findings.append(f"[GitHub Code Search] {code_text[:500]}")
    except WarRoomToolError as exc:
        logger.warning("Code search failed: %s", exc)
        findings.append(f"[GitHub Code Search] Error: {exc}")

    # Search issues
    try:
        issue_results = await client.call_tool("search_issues", {"q": query})
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
                findings.append(f"[GitHub Issues] {len(items)} results:\n" + "\n".join(hits))
            else:
                findings.append(f"[GitHub Issues] {issue_text[:500]}")
        except (json.JSONDecodeError, TypeError):
            findings.append(f"[GitHub Issues] {issue_text[:500]}")
    except WarRoomToolError as exc:
        logger.warning("Issue search failed: %s", exc)
        findings.append(f"[GitHub Issues] Error: {exc}")

    summary = "\n".join(findings) if findings else "[GitHub] No results found."
    return {
        "findings": state.get("findings", []) + [summary],
        "messages": [AIMessage(content=summary)],
    }
