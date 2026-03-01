"""Shared pytest fixtures — clears caches between tests for isolation."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── Cache isolation (autouse) ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Reset the cached Settings singleton before each test."""
    from war_room_copilot.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clear_graph_llm_cache() -> None:
    """Reset the cached graph LLM before each test."""
    from war_room_copilot.graph.llm import get_graph_llm

    get_graph_llm.cache_clear()


@pytest.fixture(autouse=True)
def _reset_incident_graph() -> None:
    """Reset the lazy-loaded incident graph before each test."""
    import war_room_copilot.graph.incident_graph as ig

    ig._incident_graph = None


@pytest.fixture(autouse=True)
def _reset_mcp_client() -> None:
    """Reset the global MCP client between tests."""
    import war_room_copilot.graph.nodes.github_research as gr

    gr._mcp_client = None


@pytest.fixture(autouse=True)
def _reset_backboard_globals() -> None:
    """Reset backboard client singletons between tests."""
    import war_room_copilot.tools.backboard as bb

    bb._client = None
    bb._assistant_id = None


# ── Shared helpers ─────────────────────────────────────────────────────────────


def make_incident_state(**overrides: Any) -> dict[str, Any]:
    """Build a minimal IncidentState dict for testing graph nodes."""
    base: dict[str, Any] = {
        "messages": [],
        "transcript": [],
        "findings": [],
        "decisions": [],
        "speakers": {},
        "routed_skill": "respond",
        "query": "",
    }
    base.update(overrides)
    return base


# ── Mock LLM fixture ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_llm_response() -> MagicMock:
    """A configurable mock LLM response object."""
    response = MagicMock()
    response.content = "mocked LLM response"
    return response


@pytest.fixture
def mock_graph_llm(mock_llm_response: MagicMock) -> AsyncMock:
    """Return an AsyncMock LLM whose ainvoke returns mock_llm_response."""
    llm = AsyncMock()
    llm.ainvoke.return_value = mock_llm_response
    return llm
