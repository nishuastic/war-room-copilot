"""GitHub tools for querying repos during incidents."""

from __future__ import annotations

import asyncio
import os
from functools import lru_cache

from github import Auth, Github
from github.GithubException import GithubException
from livekit.agents import ToolError, function_tool

from ..config import GITHUB_ALLOWED_REPOS

MAX_OUTPUT_CHARS = 2000


@lru_cache(maxsize=1)
def _get_github_client() -> Github:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise ToolError("GITHUB_TOKEN environment variable is not set")
    return Github(auth=Auth.Token(token))


def _resolve_repo(repo: str | None) -> str:
    if repo:
        if GITHUB_ALLOWED_REPOS and repo not in GITHUB_ALLOWED_REPOS:
            raise ToolError(f"Repo '{repo}' is not in the allowed list: {GITHUB_ALLOWED_REPOS}")
        return repo
    if len(GITHUB_ALLOWED_REPOS) == 1:
        return GITHUB_ALLOWED_REPOS[0]
    if GITHUB_ALLOWED_REPOS:
        raise ToolError(f"Multiple repos configured. Specify which one: {GITHUB_ALLOWED_REPOS}")
    raise ToolError("No repos configured. Set GITHUB_ALLOWED_REPOS in config.py")


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n... (truncated)"


@function_tool()
async def search_code(query: str, repo: str | None = None) -> str:
    """Search for code in a GitHub repo. Use to find where errors, functions, or config live."""
    repo_name = _resolve_repo(repo)
    g = _get_github_client()

    def _search() -> str:
        full_query = f"{query} repo:{repo_name}"
        results = g.search_code(full_query)
        lines: list[str] = []
        for item in results[:10]:  # type: ignore[var-annotated]
            lines.append(f"- {item.path} (score: {item.score})")
        if not lines:
            return "No results found."
        return "\n".join(lines)

    try:
        return _truncate(await asyncio.to_thread(_search))
    except GithubException as e:
        raise ToolError(f"GitHub API error: {e.data}") from e


@function_tool()
async def get_recent_commits(repo: str | None = None, branch: str = "main", count: int = 10) -> str:
    """Get recent commits on a branch. Use to see what changed recently."""
    repo_name = _resolve_repo(repo)
    g = _get_github_client()

    def _fetch() -> str:
        r = g.get_repo(repo_name)
        commits = r.get_commits(sha=branch)[:count]
        lines: list[str] = []
        for c in commits:  # type: ignore[var-annotated]
            sha = c.sha[:7]
            msg = (c.commit.message.split("\n")[0])[:80]
            author = c.commit.author.name if c.commit.author else "unknown"
            lines.append(f"- {sha} {author}: {msg}")
        return "\n".join(lines) if lines else "No commits found."

    try:
        return _truncate(await asyncio.to_thread(_fetch))
    except GithubException as e:
        raise ToolError(f"GitHub API error: {e.data}") from e


@function_tool()
async def get_commit_diff(commit_sha: str, repo: str | None = None) -> str:
    """Get the full diff for a specific commit. Use to inspect a suspicious change."""
    repo_name = _resolve_repo(repo)
    g = _get_github_client()

    def _fetch() -> str:
        r = g.get_repo(repo_name)
        commit = r.get_commit(commit_sha)
        files = list(commit.files) if commit.files else []
        lines: list[str] = [
            f"Commit: {commit.sha[:7]} by "
            f"{commit.commit.author.name if commit.commit.author else 'unknown'}",
            f"Message: {commit.commit.message.split(chr(10))[0]}",
            f"Files changed: {len(files)}",
            "",
        ]
        for f in files:
            lines.append(f"--- {f.filename} ({f.status}, +{f.additions}/-{f.deletions})")
            if f.patch:
                lines.append(f.patch)
            lines.append("")
        return "\n".join(lines)

    try:
        return _truncate(await asyncio.to_thread(_fetch))
    except GithubException as e:
        raise ToolError(f"GitHub API error: {e.data}") from e


@function_tool()
async def list_pull_requests(
    state: str = "closed", repo: str | None = None, count: int = 10
) -> str:
    """List recent pull requests. Use to find recently merged PRs that may have caused issues."""
    repo_name = _resolve_repo(repo)
    g = _get_github_client()

    def _fetch() -> str:
        r = g.get_repo(repo_name)
        prs = r.get_pulls(state=state, sort="updated", direction="desc")[:count]
        lines: list[str] = []
        for pr in prs:  # type: ignore[var-annotated]
            merged = " [MERGED]" if pr.merged else ""
            author = pr.user.login if pr.user else "unknown"
            lines.append(f"- #{pr.number} {pr.title}{merged} by {author}")
        return "\n".join(lines) if lines else "No pull requests found."

    try:
        return _truncate(await asyncio.to_thread(_fetch))
    except GithubException as e:
        raise ToolError(f"GitHub API error: {e.data}") from e


@function_tool()
async def search_issues(query: str, repo: str | None = None) -> str:
    """Search GitHub issues. Use to find related bugs or past incidents."""
    repo_name = _resolve_repo(repo)
    g = _get_github_client()

    def _search() -> str:
        full_query = f"{query} repo:{repo_name}"
        results = g.search_issues(full_query)
        lines: list[str] = []
        for issue in results[:10]:  # type: ignore[var-annotated]
            state = issue.state
            lines.append(f"- #{issue.number} [{state}] {issue.title}")
        return "\n".join(lines) if lines else "No issues found."

    try:
        return _truncate(await asyncio.to_thread(_search))
    except GithubException as e:
        raise ToolError(f"GitHub API error: {e.data}") from e


@function_tool()
async def read_file(path: str, repo: str | None = None, ref: str = "main") -> str:
    """Read a file from a GitHub repo. Use to inspect config, code, or manifests."""
    repo_name = _resolve_repo(repo)
    g = _get_github_client()

    def _fetch() -> str:
        r = g.get_repo(repo_name)
        content = r.get_contents(path, ref=ref)
        if isinstance(content, list):
            return "Path is a directory: " + ", ".join(c.path for c in content)
        decoded: str = content.decoded_content.decode("utf-8", errors="replace")
        return decoded

    try:
        return _truncate(await asyncio.to_thread(_fetch))
    except GithubException as e:
        raise ToolError(f"GitHub API error: {e.data}") from e


@function_tool()
async def get_blame(path: str, repo: str | None = None) -> str:
    """Get git blame for a file. Use to find who last touched specific code."""
    repo_name = _resolve_repo(repo)
    g = _get_github_client()

    def _fetch() -> str:
        r = g.get_repo(repo_name)
        # PyGitHub doesn't have a direct blame API; use commits on the file
        commits = r.get_commits(path=path)[:10]
        lines: list[str] = [f"Recent commits touching {path}:"]
        for c in commits:  # type: ignore[var-annotated]
            sha = c.sha[:7]
            msg = (c.commit.message.split("\n")[0])[:60]
            author = c.commit.author.name if c.commit.author else "unknown"
            lines.append(f"- {sha} {author}: {msg}")
        return "\n".join(lines) if lines else "No commit history found for this file."

    try:
        return _truncate(await asyncio.to_thread(_fetch))
    except GithubException as e:
        raise ToolError(f"GitHub API error: {e.data}") from e


# ---------------------------------------------------------------------------
# Write tools — require 'repo' scope on the GitHub token
# ---------------------------------------------------------------------------


@function_tool()
async def create_github_issue(
    title: str,
    body: str,
    labels: str = "",
    repo: str | None = None,
) -> str:
    """Create a new GitHub issue. Use to track incidents, action items, or follow-ups.

    Requires GitHub token with 'repo' scope (full control of private repositories).

    Args:
        title: Issue title, e.g. 'Incident: Postgres connection pool exhausted 2026-03-01'
        body: Issue body (markdown). Include root cause, impact, and next steps.
        labels: Comma-separated label names, e.g. 'bug,incident,memory'.
            Labels must already exist in the repo.
        repo: GitHub repo in 'owner/name' format. Defaults to the configured repo.
    """
    repo_name = _resolve_repo(repo)
    g = _get_github_client()

    def _create() -> str:
        r = g.get_repo(repo_name)
        label_list = [lbl.strip() for lbl in labels.split(",") if lbl.strip()]
        if label_list:
            # Fetch existing label objects; skip any that don't exist
            existing_labels = {lbl.name for lbl in r.get_labels()}
            valid_labels = [lbl for lbl in label_list if lbl in existing_labels]
            issue = r.create_issue(title=title, body=body, labels=valid_labels)
        else:
            issue = r.create_issue(title=title, body=body)
        return f"Issue #{issue.number} created: {issue.html_url}"

    try:
        return await asyncio.to_thread(_create)
    except GithubException as e:
        raise ToolError(f"GitHub API error creating issue: {e.data}") from e


@function_tool()
async def revert_commit(commit_sha: str, repo: str | None = None) -> str:
    """Create a revert PR for a given commit SHA.

    Opens a new branch named 'revert-<sha>' and creates a pull request to revert the commit.
    Requires GitHub token with 'repo' scope.

    Args:
        commit_sha: The commit SHA to revert (full or abbreviated, e.g. '14b6316')
        repo: GitHub repo in 'owner/name' format. Defaults to the configured repo.
    """
    repo_name = _resolve_repo(repo)
    g = _get_github_client()

    def _revert() -> str:

        r = g.get_repo(repo_name)
        # Resolve abbreviated SHA to full
        commit = r.get_commit(commit_sha)
        full_sha = commit.sha
        short_sha = full_sha[:7]
        commit_msg = commit.commit.message.split("\n")[0][:60]

        # Create revert branch from default branch
        default_branch = r.default_branch
        base_ref = r.get_branch(default_branch)
        branch_name = f"revert-{short_sha}"

        # Create branch
        r.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_ref.commit.sha)

        # Create an empty revert commit (note: GitHub API doesn't do git revert natively;
        # this creates a PR with instructions for the engineer to complete the revert)
        pr_body = (
            f"## Revert: {commit_msg}\n\n"
            f"This PR reverts commit `{short_sha}` ({full_sha}).\n\n"
            f"**To complete the revert**, run locally:\n"
            f"```bash\n"
            f"git fetch origin\n"
            f"git checkout {branch_name}\n"
            f"git revert {full_sha} --no-edit\n"
            f"git push origin {branch_name}\n"
            f"```\n\n"
            f"Branch `{branch_name}` has been created from `{default_branch}` head."
        )

        pr = r.create_pull(
            title=f"Revert: {commit_msg} ({short_sha})",
            body=pr_body,
            head=branch_name,
            base=default_branch,
        )
        return (
            f"Revert PR #{pr.number} created: {pr.html_url}\n"
            f"Branch '{branch_name}' ready. "
            "Follow the instructions in the PR to complete the revert."
        )

    try:
        return await asyncio.to_thread(_revert)
    except GithubException as e:
        raise ToolError(f"GitHub API error creating revert PR: {e.data}") from e


@function_tool()
async def close_pull_request(pr_number: int, repo: str | None = None) -> str:
    """Close (without merging) an open pull request.

    Use to close a bad or superseded PR during an incident.
    Requires GitHub token with 'repo' scope.

    Args:
        pr_number: Pull request number, e.g. 42
        repo: GitHub repo in 'owner/name' format. Defaults to the configured repo.
    """
    repo_name = _resolve_repo(repo)
    g = _get_github_client()

    def _close() -> str:
        r = g.get_repo(repo_name)
        pr = r.get_pull(pr_number)
        if pr.state == "closed":
            return f"PR #{pr_number} is already closed."
        pr.edit(state="closed")
        return f"PR #{pr_number} '{pr.title}' has been closed (not merged)."

    try:
        return await asyncio.to_thread(_close)
    except GithubException as e:
        raise ToolError(f"GitHub API error closing PR: {e.data}") from e
