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


async def _get_recent_commits(client: GitHubMCPClient) -> str:
    """Fetch recent commits for the default repo."""
    cfg = get_settings()
    owner = cfg.default_repo_owner
    repo = cfg.default_repo_name
    if not owner or not repo:
        return "[GitHub Commits] No default repo configured."

    try:
        result = await client.call_tool(
            "list_commits",
            {"owner": owner, "repo": repo, "perPage": 10},
        )
        text = _content_to_text(result)
        try:
            commits = json.loads(text)
            if isinstance(commits, list):
                lines = []
                for c in commits[:10]:
                    sha = c.get("sha", "?")[:7]
                    msg = c.get("commit", {}).get("message", "?").splitlines()[0]
                    lines.append(f"  - {sha} {msg}")
                return f"[GitHub Recent Commits] {len(commits)} commits:\n" + "\n".join(lines)
        except (json.JSONDecodeError, TypeError):
            pass
        return f"[GitHub Recent Commits] {text[:500]}"
    except Exception as exc:
        return f"[GitHub Recent Commits] Error: {exc}"


async def _generate_hypothesis(query: str, findings: list[str], transcript: list[str]) -> str:
    """Use the graph LLM to generate a root cause hypothesis from findings + transcript."""
    from war_room_copilot.graph.llm import get_graph_llm

    llm = get_graph_llm()
    findings_text = "\n".join(findings)
    transcript_text = "\n".join(transcript[-20:]) if transcript else "(no transcript)"

    prompt = (
        "You are an SRE analyzing a production incident. Based on the GitHub research "
        "findings and the recent incident transcript, generate a root cause hypothesis.\n\n"
        f"## Incident Query\n{query}\n\n"
        f"## GitHub Findings\n{findings_text}\n\n"
        f"## Recent Transcript\n{transcript_text}\n\n"
        "## Instructions\n"
        "1. Correlate the code changes, issues, and search results with what was discussed.\n"
        "2. Generate a concise root cause hypothesis (2-3 sentences).\n"
        "3. List supporting evidence (bullet points).\n"
        "4. Rate your confidence: LOW / MEDIUM / HIGH.\n\n"
        "Format:\n"
        "**Hypothesis:** <your hypothesis>\n"
        "**Evidence:**\n- <point 1>\n- <point 2>\n"
        "**Confidence:** <LOW|MEDIUM|HIGH>"
    )

    from langchain_core.messages import HumanMessage

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return f"[Root Cause Hypothesis]\n{response.content}"


async def github_research_node(state: IncidentState) -> dict[str, Any]:
    """Research GitHub for context relevant to the current query.

    Calls search_code, search_issues, and recent commits in parallel,
    then generates a root cause hypothesis correlating findings with
    the incident transcript.
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

    # Run code search, issue search, and recent commits in parallel
    findings: list[str] = []
    code_result, issue_result, commits_result = await asyncio.gather(
        _search_code(client, query),
        _search_issues(client, query),
        _get_recent_commits(client),
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

    if isinstance(commits_result, str):
        findings.append(commits_result)
    elif isinstance(commits_result, Exception):
        logger.warning("Commits fetch failed: %s", commits_result)
        findings.append(f"[GitHub Commits] Error: {commits_result}")

    # Generate root cause hypothesis by correlating findings with transcript
    transcript = state.get("transcript", [])
    try:
        hypothesis = await _generate_hypothesis(query, findings, transcript)
        findings.append(hypothesis)
    except Exception as exc:
        logger.warning("Hypothesis generation failed: %s", exc)
        findings.append(f"[Root Cause Hypothesis] Could not generate: {exc}")

    summary = "\n".join(findings) if findings else "[GitHub] No results found."
    return {
        "findings": [summary],
        "messages": [AIMessage(content=summary)],
    }
