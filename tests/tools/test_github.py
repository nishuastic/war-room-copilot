"""Tests for GitHub tool parsers and get_repo_context facade."""

from __future__ import annotations

from unittest.mock import MagicMock

from war_room_copilot.tools.github import (
    _commit_from_dict,
    _issue_from_dict,
    _parse_list,
    _pr_from_dict,
)

# ── _issue_from_dict ──────────────────────────────────────────────────────────


def test_issue_from_dict_full() -> None:
    """All fields present produce a complete GitHubIssue."""
    d = {
        "number": 42,
        "title": "Server crash",
        "state": "open",
        "body": "details here",
        "labels": [{"name": "bug"}, {"name": "P0"}],
        "created_at": "2026-01-01T00:00:00Z",
        "html_url": "https://github.com/org/repo/issues/42",
    }
    issue = _issue_from_dict(d)
    assert issue.number == 42
    assert issue.title == "Server crash"
    assert issue.state == "open"
    assert issue.body == "details here"
    assert issue.labels == ["bug", "P0"]
    assert issue.url == "https://github.com/org/repo/issues/42"


def test_issue_from_dict_missing_keys() -> None:
    """Missing keys fall back to safe defaults."""
    issue = _issue_from_dict({})
    assert issue.number == 0
    assert issue.title == ""
    assert issue.state == ""
    assert issue.body is None
    assert issue.labels == []
    assert issue.url == ""


def test_issue_from_dict_labels_non_dict_filtered() -> None:
    """Non-dict label entries are silently dropped."""
    d = {
        "number": 1,
        "title": "t",
        "state": "open",
        "labels": ["bug", {"name": "P0"}, 42],
    }
    issue = _issue_from_dict(d)
    assert issue.labels == ["P0"]


# ── _pr_from_dict ─────────────────────────────────────────────────────────────


def test_pr_from_dict_full() -> None:
    """All fields present produce a complete GitHubPR."""
    d = {
        "number": 10,
        "title": "Fix bug",
        "state": "open",
        "body": "fixes #42",
        "head": {"ref": "fix/crash"},
        "base": {"ref": "main"},
        "merged_at": None,
        "html_url": "https://github.com/org/repo/pull/10",
    }
    pr = _pr_from_dict(d)
    assert pr.number == 10
    assert pr.head_branch == "fix/crash"
    assert pr.base_branch == "main"


def test_pr_from_dict_none_head_base() -> None:
    """Explicit None for head/base is handled via `or {}` guard."""
    d = {"number": 1, "title": "t", "state": "open", "head": None, "base": None}
    pr = _pr_from_dict(d)
    assert pr.head_branch == ""
    assert pr.base_branch == ""


# ── _commit_from_dict ─────────────────────────────────────────────────────────


def test_commit_from_dict_full() -> None:
    """SHA is truncated to 7 chars and only first line of message is kept."""
    d = {
        "sha": "abc1234567890",
        "commit": {
            "message": "fix: resolve crash\n\nLonger description here",
            "author": {"name": "Alice", "date": "2026-01-01T00:00:00Z"},
        },
        "html_url": "https://github.com/org/repo/commit/abc1234567890",
    }
    commit = _commit_from_dict(d)
    assert commit.sha == "abc1234"
    assert commit.message == "fix: resolve crash"
    assert commit.author == "Alice"


def test_commit_from_dict_multiline_message() -> None:
    """Only the first line of a multiline message is kept."""
    d = {"sha": "aaa", "commit": {"message": "line1\nline2\nline3"}}
    commit = _commit_from_dict(d)
    assert commit.message == "line1"


def test_commit_from_dict_empty_message() -> None:
    """Empty commit message returns empty string (not IndexError)."""
    d = {"sha": "aaa", "commit": {"message": ""}}
    commit = _commit_from_dict(d)
    assert commit.message == ""


def test_commit_from_dict_none_sha() -> None:
    """None sha is handled via `or ''` guard."""
    d = {"sha": None, "commit": {"message": "test"}}
    commit = _commit_from_dict(d)
    assert commit.sha == ""


# ── _parse_list ───────────────────────────────────────────────────────────────


def test_parse_list_base_exception() -> None:
    """BaseException input (from gather return_exceptions) returns []."""
    result = _parse_list(RuntimeError("timeout"), _issue_from_dict)
    assert result == []


def test_parse_list_valid_json_list() -> None:
    """JSON list of dicts is parsed through the factory function."""
    block = MagicMock()
    block.text = '[{"number": 1, "title": "a", "state": "open"}]'
    result = _parse_list([block], _issue_from_dict)
    assert len(result) == 1
    assert result[0].number == 1


def test_parse_list_single_object_wrapped() -> None:
    """A single JSON object (not array) is wrapped in a list."""
    block = MagicMock()
    block.text = '{"number": 5, "title": "b", "state": "open"}'
    result = _parse_list([block], _issue_from_dict)
    assert len(result) == 1
    assert result[0].number == 5


def test_parse_list_non_dict_items_filtered() -> None:
    """Non-dict items in the JSON array are silently dropped."""
    block = MagicMock()
    block.text = '[1, "str", {"number": 2, "title": "c", "state": "open"}]'
    result = _parse_list([block], _issue_from_dict)
    assert len(result) == 1
    assert result[0].number == 2


def test_parse_list_invalid_json() -> None:
    """Unparseable content returns an empty list."""
    block = MagicMock()
    block.text = "not valid json at all"
    result = _parse_list([block], _issue_from_dict)
    assert result == []
