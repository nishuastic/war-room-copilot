"""Tests for Settings configuration and get_settings singleton."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from war_room_copilot.config import Settings, get_settings

# ── Settings defaults ─────────────────────────────────────────────────────────


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default values match expected development configuration."""
    # Clear env vars that might override defaults
    for key in ("LLM_PROVIDER", "LLM_MODEL", "PLATFORM"):
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.platform == "livekit"
    assert s.llm_provider == "openai"
    assert s.llm_model == ""
    assert s.github_mcp_timeout == 30.0
    assert s.speechmatics_max_speakers == 10
    assert s.repo_context_max_issues == 10


def test_settings_valid_platform_literals() -> None:
    """All valid platform values are accepted."""
    for platform in ("livekit", "google_meet", "zoom"):
        s = Settings(platform=platform, _env_file=None)  # type: ignore[call-arg]
        assert s.platform == platform


def test_settings_invalid_platform_rejected() -> None:
    """Invalid platform raises ValidationError."""
    with pytest.raises(ValidationError):
        Settings(platform="discord", _env_file=None)  # type: ignore[call-arg]


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables override defaults."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "custom-model")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.llm_provider == "anthropic"
    assert s.llm_model == "custom-model"


def test_get_settings_cached() -> None:
    """get_settings returns the same instance on consecutive calls."""
    a = get_settings()
    b = get_settings()
    assert a is b
