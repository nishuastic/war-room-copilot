"""High-level GitHub operations — the public facade for the rest of the codebase."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from war_room_copilot.config import get_settings
from war_room_copilot.models import GitHubCommit, GitHubIssue, GitHubPR, RepoContext
from war_room_copilot.tools.github_mcp import GitHubMCPClient

logger = logging.getLogger("war-room-copilot.tools.github")


async def get_repo_context(
    client: GitHubMCPClient,
    owner: str | None = None,
    repo: str | None = None,
    max_issues: int | None = None,
    max_prs: int | None = None,
    max_commits: int | None = None,
) -> RepoContext:
    """Fetch issues, pull requests, and recent commits in parallel.

    Uses asyncio.gather with return_exceptions=True so a failure in one
    endpoint (e.g., rate limit on issues) doesn't prevent the others from
    returning data.
    """
    cfg = get_settings()
    owner = owner or cfg.default_repo_owner
    repo = repo or cfg.default_repo_name

    if not owner or not repo:
        raise ValueError(
            "owner and repo must be provided, or set DEFAULT_REPO_OWNER and "
            "DEFAULT_REPO_NAME in your environment."
        )

    max_issues = cfg.repo_context_max_issues if max_issues is None else max_issues
    max_prs = cfg.repo_context_max_prs if max_prs is None else max_prs
    max_commits = cfg.repo_context_max_commits if max_commits is None else max_commits

    results: tuple[Any, ...] = await asyncio.gather(
        client.call_tool("list_issues", {"owner": owner, "repo": repo, "perPage": max_issues}),
        client.call_tool("list_pull_requests", {"owner": owner, "repo": repo, "perPage": max_prs}),
        client.call_tool("list_commits", {"owner": owner, "repo": repo, "perPage": max_commits}),
        return_exceptions=True,
    )

    return RepoContext(
        owner=owner,
        repo=repo,
        issues=_parse_issues(results[0]),
        pull_requests=_parse_prs(results[1]),
        commits=_parse_commits(results[2]),
    )


# ── Parsers ────────────────────────────────────────────────────────────────────
# MCP returns content blocks whose .text field is JSON from GitHub's REST API.
# These parsers are tolerant — a partial result is better than a crash.


def _parse_issues(raw: Any) -> list[GitHubIssue]:
    return _parse_list(raw, _issue_from_dict)


def _parse_prs(raw: Any) -> list[GitHubPR]:
    return _parse_list(raw, _pr_from_dict)


def _parse_commits(raw: Any) -> list[GitHubCommit]:
    return _parse_list(raw, _commit_from_dict)


def _parse_list(raw: Any, factory: Any) -> list[Any]:
    if isinstance(raw, BaseException):
        logger.warning("Tool call failed, returning empty list: %s", raw)
        return []
    try:
        if raw and isinstance(raw, list):
            text = " ".join(block.text if hasattr(block, "text") else str(block) for block in raw)
        else:
            text = str(raw)
        data = json.loads(text)
        if not isinstance(data, list):
            data = [data]
        return [factory(item) for item in data if isinstance(item, dict)]
    except Exception:
        logger.exception("Failed to parse tool response")
        return []


def _issue_from_dict(d: dict[str, Any]) -> GitHubIssue:
    return GitHubIssue(
        number=d.get("number", 0),
        title=d.get("title", ""),
        state=d.get("state", ""),
        body=d.get("body"),
        labels=[lbl["name"] for lbl in d.get("labels", []) if isinstance(lbl, dict)],
        created_at=d.get("created_at"),
        url=d.get("html_url", ""),
    )


def _pr_from_dict(d: dict[str, Any]) -> GitHubPR:
    head = d.get("head", {}) or {}
    base = d.get("base", {}) or {}
    return GitHubPR(
        number=d.get("number", 0),
        title=d.get("title", ""),
        state=d.get("state", ""),
        body=d.get("body"),
        head_branch=head.get("ref", ""),
        base_branch=base.get("ref", ""),
        merged_at=d.get("merged_at"),
        url=d.get("html_url", ""),
    )


def _commit_from_dict(d: dict[str, Any]) -> GitHubCommit:
    commit_data = d.get("commit", {}) or {}
    author_data = commit_data.get("author", {}) or {}
    return GitHubCommit(
        sha=(d.get("sha") or "")[:7],
        message=(commit_data.get("message", "") or "").splitlines()[0],
        author=author_data.get("name", ""),
        committed_at=author_data.get("date"),
        url=d.get("html_url", ""),
    )
