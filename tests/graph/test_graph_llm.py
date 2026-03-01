"""Tests for graph LLM factory — LangChain model creation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from war_room_copilot.graph.llm import get_graph_llm

# ── get_graph_llm ─────────────────────────────────────────────────────────────


def test_get_graph_llm_unknown_provider_raises() -> None:
    """Unknown provider raises ValueError."""
    mock_settings = MagicMock()
    mock_settings.llm_provider = "unknown"
    mock_settings.llm_model = ""

    with patch("war_room_copilot.graph.llm.get_settings", return_value=mock_settings):
        with pytest.raises(ValueError, match="Unsupported graph LLM provider"):
            get_graph_llm()


def test_get_graph_llm_openai_default_model() -> None:
    """OpenAI provider with empty model uses gpt-4o-mini."""
    mock_settings = MagicMock()
    mock_settings.llm_provider = "openai"
    mock_settings.llm_model = ""

    mock_chat = MagicMock()

    with (
        patch("war_room_copilot.graph.llm.get_settings", return_value=mock_settings),
        patch("langchain_openai.ChatOpenAI", mock_chat),
    ):
        get_graph_llm()

    mock_chat.assert_called_once_with(model="gpt-4o-mini", temperature=0)


def test_get_graph_llm_openai_custom_model() -> None:
    """OpenAI provider with custom model uses that model."""
    mock_settings = MagicMock()
    mock_settings.llm_provider = "openai"
    mock_settings.llm_model = "gpt-4-turbo"

    mock_chat = MagicMock()

    with (
        patch("war_room_copilot.graph.llm.get_settings", return_value=mock_settings),
        patch("langchain_openai.ChatOpenAI", mock_chat),
    ):
        get_graph_llm()

    mock_chat.assert_called_once_with(model="gpt-4-turbo", temperature=0)


def test_get_graph_llm_cache_returns_same() -> None:
    """Consecutive calls return the same instance."""
    mock_settings = MagicMock()
    mock_settings.llm_provider = "openai"
    mock_settings.llm_model = ""

    with patch("war_room_copilot.graph.llm.get_settings", return_value=mock_settings):
        a = get_graph_llm()
        b = get_graph_llm()

    assert a is b
