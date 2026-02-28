"""GitHub tool wrappers — search code, commits, PRs, blame."""

from __future__ import annotations

import logging
from typing import Any

from github import Github

from war_room_copilot.config import settings

logger = logging.getLogger("war-room-copilot.tools.github")


class GitHubTool:
    def __init__(self) -> None:
        self._gh = Github(settings.github_token) if settings.github_token else None
        self._repo_name = settings.github_repo

    def _get_repo(self) -> Any:
        if not self._gh or not self._repo_name:
            raise RuntimeError("GitHub not configured (set GITHUB_TOKEN and GITHUB_REPO)")
        return self._gh.get_repo(self._repo_name)

    def search_code(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search code in the repository."""
        try:
            self._get_repo()  # validate repo exists
            results = self._gh.search_code(f"{query} repo:{self._repo_name}")  # type: ignore[union-attr]
            return [
                {"path": r.path, "url": r.html_url, "snippet": r.decoded_content.decode()[:500]}
                for r in list(results)[:limit]
            ]
        except Exception:
            logger.warning("GitHub code search failed", exc_info=True)
            return []

    def recent_commits(self, limit: int = 10, path: str | None = None) -> list[dict[str, str]]:
        """Get recent commits, optionally filtered by path."""
        try:
            repo = self._get_repo()
            kwargs: dict[str, Any] = {}
            if path:
                kwargs["path"] = path
            commits = repo.get_commits(**kwargs)
            return [
                {
                    "sha": c.sha[:8],
                    "message": c.commit.message.split("\n")[0],
                    "author": c.commit.author.name or "unknown",
                    "date": c.commit.author.date.isoformat(),
                }
                for c in list(commits)[:limit]
            ]
        except Exception:
            logger.warning("GitHub commits fetch failed", exc_info=True)
            return []

    def get_pr_diff(self, pr_number: int) -> dict[str, Any]:
        """Get PR details and diff."""
        try:
            repo = self._get_repo()
            pr = repo.get_pull(pr_number)
            files = [
                {"filename": f.filename, "changes": f.changes, "patch": (f.patch or "")[:500]}
                for f in pr.get_files()
            ]
            return {
                "title": pr.title,
                "state": pr.state,
                "author": pr.user.login,
                "files": files,
                "body": (pr.body or "")[:1000],
            }
        except Exception:
            logger.warning("GitHub PR fetch failed", exc_info=True)
            return {}

    def blame(self, path: str) -> list[dict[str, str]]:
        """Get git blame for a file (simplified — returns recent commits touching the file)."""
        return self.recent_commits(limit=5, path=path)


# OpenAI function calling tool definitions
GITHUB_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_github",
            "description": "Search code in the GitHub repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recent_commits",
            "description": "Get recent commits, optionally filtered by file path",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10},
                    "path": {"type": "string", "description": "Optional file path filter"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pr_diff",
            "description": "Get pull request details and file diffs",
            "parameters": {
                "type": "object",
                "properties": {
                    "pr_number": {"type": "integer", "description": "PR number"},
                },
                "required": ["pr_number"],
            },
        },
    },
]
