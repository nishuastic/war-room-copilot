"""Configuration and environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    # LiveKit
    livekit_url: str = field(
        default_factory=lambda: os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
    )
    livekit_api_key: str = field(
        default_factory=lambda: os.environ.get("LIVEKIT_API_KEY", "devkey")
    )
    livekit_api_secret: str = field(
        default_factory=lambda: os.environ.get("LIVEKIT_API_SECRET", "secret")
    )

    # STT / LLM / TTS
    speechmatics_api_key: str = field(
        default_factory=lambda: os.environ.get("SPEECHMATICS_API_KEY", "")
    )
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))

    # Memory
    backboard_api_key: str = field(default_factory=lambda: os.environ.get("BACKBOARD_API_KEY", ""))
    backboard_base_url: str = field(
        default_factory=lambda: os.environ.get("BACKBOARD_BASE_URL", "https://api.backboard.io")
    )

    # Tools
    github_token: str = field(default_factory=lambda: os.environ.get("GITHUB_TOKEN", ""))
    github_repo: str = field(default_factory=lambda: os.environ.get("GITHUB_REPO", ""))

    # Tracing
    langsmith_api_key: str = field(default_factory=lambda: os.environ.get("LANGSMITH_API_KEY", ""))

    # Thresholds
    interjection_confidence_speak: float = 0.7
    interjection_confidence_dashboard: float = 0.4
    silence_threshold_seconds: float = 1.5
    transcript_window_seconds: float = 600.0  # 10 min sliding window
    contradict_check_interval_seconds: float = 10.0

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()
