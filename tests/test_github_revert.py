"""Tests for revert_commit in tools.github."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from github import GithubException
from livekit.agents import ToolError

from src.war_room_copilot.tools.github import revert_commit


def _make_repo_mock(
    *,
    head_sha: str = "abc1234567890",
    commit_sha: str = "abc1234567890",
    parent_sha: str = "def0000000000",
    parent_count: int = 1,
    default_branch: str = "main",
    branch_exists: bool = False,
    open_pr: MagicMock | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Build a MagicMock repo and github client for revert_commit tests."""
    repo = MagicMock()
    repo.default_branch = default_branch
    repo.owner.login = "testowner"

    # Commit to revert
    commit = MagicMock()
    commit.sha = commit_sha
    commit.commit.message = "Break everything\ndetails here"
    parents = [MagicMock(sha=parent_sha) for _ in range(parent_count)]
    commit.commit.parents = parents
    repo.get_commit.return_value = commit

    # Default branch HEAD
    branch_ref = MagicMock()
    branch_ref.commit.sha = head_sha
    repo.get_branch.return_value = branch_ref

    # Branch existence check
    if branch_exists:
        repo.get_git_ref.return_value = MagicMock()
    else:
        repo.get_git_ref.side_effect = GithubException(
            404, data={"message": "Not Found"}, headers={}
        )

    # Open PRs for the branch
    if open_pr:
        repo.get_pulls.return_value = [open_pr]
    else:
        repo.get_pulls.return_value = []

    # Git Data API mocks
    parent_tree = MagicMock()
    parent_git_commit = MagicMock()
    parent_git_commit.tree = parent_tree
    head_git_commit = MagicMock()

    def _get_git_commit(sha: str) -> MagicMock:
        if sha == parent_sha:
            return parent_git_commit
        return head_git_commit

    repo.get_git_commit.side_effect = _get_git_commit

    revert_commit_obj = MagicMock()
    revert_commit_obj.sha = "revert000000"
    repo.create_git_commit.return_value = revert_commit_obj

    # create_git_ref returns a ref object with edit/delete
    new_branch_ref = MagicMock()
    repo.create_git_ref.return_value = new_branch_ref

    # PR mock
    pr = MagicMock()
    pr.number = 42
    pr.html_url = "https://github.com/testowner/testrepo/pull/42"
    repo.create_pull.return_value = pr

    # Github client
    g = MagicMock()
    g.get_repo.return_value = repo

    return repo, g


@pytest.fixture()
def _patch_config():
    """Ensure auto-merge is on and repo config is set for tests."""
    with (
        patch("src.war_room_copilot.tools.github.GITHUB_REVERT_AUTO_MERGE", True),
        patch("src.war_room_copilot.tools.github.GITHUB_ALLOWED_REPOS", ["testowner/testrepo"]),
    ):
        yield


class TestRevertCommitHeadHappyPath:
    """HEAD commit → revert commit created, PR merged, branch cleaned up."""

    async def test_head_revert_merged(self, _patch_config: None) -> None:
        repo, g = _make_repo_mock(
            head_sha="abc1234567890",
            commit_sha="abc1234567890",
            parent_sha="def0000000000",
        )
        with patch("src.war_room_copilot.tools.github._get_github_client", return_value=g):
            result = await revert_commit.__wrapped__(commit_sha="abc1234")

        # Verify revert commit was created with a Revert message
        repo.create_git_commit.assert_called_once()
        call_args = repo.create_git_commit.call_args
        msg = call_args.kwargs.get("message") or call_args.args[0]
        assert "Revert" in msg

        # Verify PR was created and merged
        repo.create_pull.assert_called_once()
        pr = repo.create_pull.return_value
        pr.merge.assert_called_once_with(merge_method="squash")

        assert "created and merged" in result
        assert "#42" in result


class TestRevertCommitNonHead:
    """Non-HEAD commit → PR created with instructions, no auto-merge."""

    async def test_non_head_creates_pr_with_instructions(self, _patch_config: None) -> None:
        repo, g = _make_repo_mock(
            head_sha="fff9999999999",
            commit_sha="abc1234567890",
            parent_sha="def0000000000",
        )
        # get_git_ref should fail (no existing branch)
        repo.get_git_ref.side_effect = GithubException(
            404, data={"message": "Not Found"}, headers={}
        )

        with patch("src.war_room_copilot.tools.github._get_github_client", return_value=g):
            result = await revert_commit.__wrapped__(commit_sha="abc1234")

        # Verify PR was created but NOT merged
        repo.create_pull.assert_called_once()
        pr = repo.create_pull.return_value
        pr.merge.assert_not_called()

        # No revert commit via Git Data API
        repo.create_git_commit.assert_not_called()

        assert "isn't the latest" in result


class TestRevertCommitMergeCommit:
    """Merge commit → ToolError raised."""

    async def test_merge_commit_raises(self, _patch_config: None) -> None:
        _, g = _make_repo_mock(parent_count=2)

        with (
            patch("src.war_room_copilot.tools.github._get_github_client", return_value=g),
            pytest.raises(ToolError, match="merge commit"),
        ):
            await revert_commit.__wrapped__(commit_sha="abc1234")


class TestRevertCommitExistingPR:
    """Existing branch with open PR → returns early with PR URL."""

    async def test_existing_pr_returns_early(self, _patch_config: None) -> None:
        existing_pr = MagicMock()
        existing_pr.number = 99
        existing_pr.html_url = "https://github.com/testowner/testrepo/pull/99"

        repo, g = _make_repo_mock(branch_exists=True, open_pr=existing_pr)
        # Reset side_effect so get_git_ref succeeds
        repo.get_git_ref.side_effect = None
        repo.get_git_ref.return_value = MagicMock()

        with patch("src.war_room_copilot.tools.github._get_github_client", return_value=g):
            result = await revert_commit.__wrapped__(commit_sha="abc1234")

        # Should not create a new PR
        repo.create_pull.assert_not_called()
        assert "already exists" in result
        assert "#99" in result


class TestRevertCommitStaleBranch:
    """Stale branch (no open PR) → branch deleted and recreated."""

    async def test_stale_branch_deleted(self, _patch_config: None) -> None:
        repo, g = _make_repo_mock(
            head_sha="abc1234567890",
            commit_sha="abc1234567890",
            branch_exists=True,
        )
        # get_git_ref should succeed (branch exists) then succeed again for delete
        stale_ref = MagicMock()
        new_ref = MagicMock()

        call_count = 0

        def _get_git_ref(ref: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return stale_ref  # branch existence check
            if call_count == 2:
                return stale_ref  # for delete call
            return new_ref  # subsequent calls

        repo.get_git_ref.side_effect = _get_git_ref
        repo.get_pulls.return_value = []  # no open PR

        with patch("src.war_room_copilot.tools.github._get_github_client", return_value=g):
            result = await revert_commit.__wrapped__(commit_sha="abc1234")

        # Stale branch ref should have been deleted
        stale_ref.delete.assert_called_once()

        # New PR should be created
        repo.create_pull.assert_called_once()
        assert "created and merged" in result


class TestRevertCommitFailureCleanup:
    """Failure during commit creation → branch cleaned up."""

    async def test_branch_cleaned_up_on_failure(self, _patch_config: None) -> None:
        repo, g = _make_repo_mock(
            head_sha="abc1234567890",
            commit_sha="abc1234567890",
        )
        repo.create_git_commit.side_effect = GithubException(
            500, data={"message": "Internal error"}, headers={}
        )

        branch_ref = MagicMock()
        repo.create_git_ref.return_value = branch_ref

        # After failure, get_git_ref is called for cleanup — return a deletable ref
        cleanup_ref = MagicMock()

        def _get_git_ref(ref: str) -> MagicMock:
            # First call checks existence (404), subsequent calls for cleanup
            if ref.startswith("heads/revert-"):
                if not hasattr(_get_git_ref, "_called"):
                    _get_git_ref._called = True  # type: ignore[attr-defined]
                    raise GithubException(404, data={"message": "Not Found"}, headers={})
                return cleanup_ref
            raise GithubException(404, data={"message": "Not Found"}, headers={})

        repo.get_git_ref.side_effect = _get_git_ref

        with (
            patch("src.war_room_copilot.tools.github._get_github_client", return_value=g),
            pytest.raises(ToolError, match="GitHub API error"),
        ):
            await revert_commit.__wrapped__(commit_sha="abc1234")

        # Branch ref cleanup should be attempted
        cleanup_ref.delete.assert_called_once()
