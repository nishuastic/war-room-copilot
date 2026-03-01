"""Shared utilities for tool modules."""

from __future__ import annotations

import asyncio
from typing import Callable, TypeVar

from livekit.agents import ToolError

from ..config import TOOL_OUTPUT_CHAR_LIMIT

T = TypeVar("T")


def truncate(text: str, limit: int = 0) -> str:
    """Truncate *text* to *limit* characters (default: ``TOOL_OUTPUT_CHAR_LIMIT``)."""
    if limit <= 0:
        limit = TOOL_OUTPUT_CHAR_LIMIT
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated at {limit} chars]"


async def run_github(fn: Callable[[], T]) -> str:
    """Run a blocking GitHub call in a thread, truncate the result, and convert
    ``GithubException`` to ``ToolError``."""
    from github.GithubException import GithubException

    try:
        result = await asyncio.to_thread(fn)
        return truncate(str(result))
    except GithubException as e:
        raise ToolError(f"GitHub API error: {e.data}") from e
