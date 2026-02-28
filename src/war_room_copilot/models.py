"""Shared Pydantic models — the contract between all modules."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

# ── OpenAI function-calling schema ─────────────────────────────────────────────


class OpenAIFunction(BaseModel):
    """OpenAI function-calling schema for a single tool."""

    name: str
    description: str
    parameters: dict[str, Any]


class OpenAITool(BaseModel):
    """Wrapper matching the OpenAI API tools list format."""

    type: str = "function"
    function: OpenAIFunction


# ── GitHub entities ────────────────────────────────────────────────────────────


class GitHubIssue(BaseModel):
    number: int
    title: str
    state: str  # "open" | "closed"
    body: str | None = None
    labels: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    url: str = ""


class GitHubPR(BaseModel):
    number: int
    title: str
    state: str  # "open" | "closed" | "merged"
    body: str | None = None
    head_branch: str = ""
    base_branch: str = ""
    merged_at: datetime | None = None
    url: str = ""


class GitHubCommit(BaseModel):
    sha: str
    message: str
    author: str = ""
    committed_at: datetime | None = None
    url: str = ""


# ── Composite snapshot ─────────────────────────────────────────────────────────


class RepoContext(BaseModel):
    """Aggregated snapshot of a repo — returned by get_repo_context()."""

    owner: str
    repo: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    issues: list[GitHubIssue] = Field(default_factory=list)
    pull_requests: list[GitHubPR] = Field(default_factory=list)
    commits: list[GitHubCommit] = Field(default_factory=list)

    def as_prompt_context(self) -> str:
        """Render a compact text block suitable for injecting into an LLM prompt."""
        lines = [f"Repo: {self.owner}/{self.repo} (as of {self.fetched_at.isoformat()})"]

        if self.issues:
            items = ", ".join(
                f'#{i.number} "{i.title}" [{",".join(i.labels)}]'
                if i.labels
                else f'#{i.number} "{i.title}"'
                for i in self.issues
            )
            lines.append(f"Open Issues ({len(self.issues)}): {items}")
        else:
            lines.append("Open Issues: none")

        if self.pull_requests:
            items = ", ".join(
                f'#{p.number} "{p.title}" ({p.head_branch} -> {p.base_branch})'
                for p in self.pull_requests
            )
            lines.append(f"Open PRs ({len(self.pull_requests)}): {items}")
        else:
            lines.append("Open PRs: none")

        if self.commits:
            items = ", ".join(f'{c.sha[:7]} "{c.message}" ({c.author})' for c in self.commits)
            lines.append(f"Recent Commits ({len(self.commits)}): {items}")
        else:
            lines.append("Recent Commits: none")

        return "\n".join(lines)
