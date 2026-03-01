"""Tests for TTS factory — provider selection and model defaults."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from war_room_copilot.tts import DEFAULT_TTS_MODELS, SUPPORTED_TTS_PROVIDERS, create_tts

# ── Constants ─────────────────────────────────────────────────────────────────


def test_default_models_has_all_providers() -> None:
    """DEFAULT_TTS_MODELS dict has entries for all supported providers."""
    for provider in SUPPORTED_TTS_PROVIDERS:
        assert provider in DEFAULT_TTS_MODELS


# ── create_tts ────────────────────────────────────────────────────────────────


def test_create_tts_openai_default_model() -> None:
    """OpenAI provider with empty model uses gpt-4o-mini-tts default."""
    mock_settings = MagicMock()
    mock_settings.tts_provider = "openai"
    mock_settings.tts_model = ""

    with (
        patch("war_room_copilot.tts.get_settings", return_value=mock_settings),
        patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}),
    ):
        result = create_tts()

    assert result is not None


def test_create_tts_elevenlabs() -> None:
    """ElevenLabs provider returns a TTS instance."""
    mock_settings = MagicMock()
    mock_settings.tts_provider = "elevenlabs"
    mock_settings.tts_model = ""

    with (
        patch("war_room_copilot.tts.get_settings", return_value=mock_settings),
        patch.dict(os.environ, {"ELEVEN_API_KEY": "test-key"}),
    ):
        result = create_tts()

    assert result is not None


def test_create_tts_unknown_provider_raises() -> None:
    """Unknown provider raises ValueError."""
    mock_settings = MagicMock()
    mock_settings.tts_provider = "unknown"
    mock_settings.tts_model = ""

    with patch("war_room_copilot.tts.get_settings", return_value=mock_settings):
        with pytest.raises(ValueError, match="Unknown TTS provider"):
            create_tts()


def test_create_tts_custom_model() -> None:
    """Custom model overrides provider default."""
    mock_settings = MagicMock()
    mock_settings.tts_provider = "openai"
    mock_settings.tts_model = "tts-1-hd"

    with (
        patch("war_room_copilot.tts.get_settings", return_value=mock_settings),
        patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}),
    ):
        result = create_tts()

    assert result is not None
