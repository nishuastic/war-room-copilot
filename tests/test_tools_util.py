"""Tests for tools._util — truncate() and run_github()."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from livekit.agents import ToolError

from src.war_room_copilot.tools._util import run_github, truncate


class TestTruncate:
    def test_short_unchanged(self) -> None:
        assert truncate("hello", limit=100) == "hello"

    def test_long_truncated(self) -> None:
        text = "a" * 3000
        result = truncate(text, limit=100)
        assert len(result) < 200
        assert result.startswith("a" * 100)
        assert "truncated" in result

    def test_custom_limit(self) -> None:
        text = "x" * 50
        result = truncate(text, limit=10)
        assert result.startswith("x" * 10)
        assert "truncated" in result

    def test_default_limit(self) -> None:
        short = "y" * 100
        assert truncate(short) == short

        long = "z" * 3000
        result = truncate(long)
        assert len(result) < 2100


class TestRunGithub:
    async def test_success(self) -> None:
        result = await run_github(lambda: "ok result")
        assert result == "ok result"

    async def test_exception(self) -> None:
        from github.GithubException import GithubException

        def _raise() -> str:
            raise GithubException(404, data={"message": "Not Found"}, headers={})

        with pytest.raises(ToolError, match="GitHub API error"):
            await run_github(_raise)

    async def test_truncates_long_result(self) -> None:
        result = await run_github(lambda: "a" * 5000)
        assert "truncated" in result
