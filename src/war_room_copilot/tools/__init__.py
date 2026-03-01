"""Tool integrations for War Room Copilot."""

from __future__ import annotations

from war_room_copilot.tools.github import get_repo_context
from war_room_copilot.tools.github_mcp import (
    BackboardAuthError,
    BackboardConnectionError,
    BackboardError,
    GitHubMCPClient,
    GitHubRateLimitError,
    LLMAuthError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    MCPConnectionError,
    MCPServerError,
    WarRoomToolError,
    mcp_tool_to_schema,
)

__all__ = [
    "BackboardAuthError",
    "BackboardConnectionError",
    "BackboardError",
    "GitHubMCPClient",
    "GitHubRateLimitError",
    "LLMAuthError",
    "LLMError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "MCPConnectionError",
    "MCPServerError",
    "WarRoomToolError",
    "get_repo_context",
    "mcp_tool_to_schema",
    "run_batch_enrichment",
    "format_enrichment_for_postmortem",
]


def __getattr__(name: str) -> object:
    """Lazy import for optional batch enrichment tools."""
    if name in ("run_batch_enrichment", "format_enrichment_for_postmortem"):
        from war_room_copilot.tools.speechmatics_batch import (
            format_enrichment_for_postmortem as _fmt,
        )
        from war_room_copilot.tools.speechmatics_batch import (
            run_batch_enrichment as _run,
        )

        _map = {
            "run_batch_enrichment": _run,
            "format_enrichment_for_postmortem": _fmt,
        }
        return _map[name]
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )
