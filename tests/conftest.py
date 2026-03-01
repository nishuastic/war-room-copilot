"""Shared pytest fixtures — clears caches between tests for isolation."""

from __future__ import annotations

import pytest


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
