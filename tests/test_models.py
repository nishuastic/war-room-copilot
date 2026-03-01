"""Tests for Pydantic models and RepoContext.as_prompt_context()."""

from __future__ import annotations

from war_room_copilot.models import GitHubCommit, GitHubIssue, GitHubPR, RepoContext

# ── Model defaults ────────────────────────────────────────────────────────────


def test_github_issue_defaults() -> None:
    """GitHubIssue has correct defaults for optional fields."""
    issue = GitHubIssue(number=1, title="t", state="open")
    assert issue.body is None
    assert issue.labels == []
    assert issue.created_at is None
    assert issue.url == ""


def test_github_pr_defaults() -> None:
    """GitHubPR has correct defaults for optional fields."""
    pr = GitHubPR(number=1, title="t", state="open")
    assert pr.body is None
    assert pr.head_branch == ""
    assert pr.base_branch == ""
    assert pr.merged_at is None


def test_github_commit_defaults() -> None:
    """GitHubCommit has correct defaults for optional fields."""
    commit = GitHubCommit(sha="abc1234", message="fix")
    assert commit.author == ""
    assert commit.committed_at is None
    assert commit.url == ""


# ── RepoContext.as_prompt_context ─────────────────────────────────────────────


def test_repo_context_prompt_context_empty() -> None:
    """Empty repo context renders 'none' for each section."""
    ctx = RepoContext(owner="org", repo="app")
    text = ctx.as_prompt_context()
    assert "Open Issues: none" in text
    assert "Open PRs: none" in text
    assert "Recent Commits: none" in text


def test_repo_context_prompt_context_full() -> None:
    """Populated context includes issues with labels, PRs, and commits."""
    ctx = RepoContext(
        owner="org",
        repo="app",
        issues=[GitHubIssue(number=1, title="Bug", state="open", labels=["bug", "P0"])],
        pull_requests=[
            GitHubPR(
                number=2,
                title="Fix",
                state="open",
                head_branch="fix",
                base_branch="main",
            )
        ],
        commits=[GitHubCommit(sha="abc1234", message="hotfix", author="Alice")],
    )
    text = ctx.as_prompt_context()
    assert '#1 "Bug" [bug,P0]' in text
    assert '#2 "Fix" (fix -> main)' in text
    assert 'abc1234 "hotfix" (Alice)' in text


def test_repo_context_prompt_context_no_labels() -> None:
    """Issue without labels omits the bracket section."""
    ctx = RepoContext(
        owner="org",
        repo="app",
        issues=[GitHubIssue(number=3, title="Task", state="open")],
    )
    text = ctx.as_prompt_context()
    assert '#3 "Task"' in text
    assert "[" not in text.split("#3")[1].split(",")[0]  # no brackets after issue
