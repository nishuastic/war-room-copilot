"""Configuration and environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Platform — "livekit", "google_meet", or "zoom"
    platform: str = Field(default="livekit")

    # LiveKit
    livekit_url: str = Field(default="ws://localhost:7880")
    livekit_api_key: str = Field(default="")
    livekit_api_secret: str = Field(default="")

    # Speech / LLM
    speechmatics_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")
    elevenlabs_api_key: str = Field(default="")

    # Integrations
    github_token: str = Field(default="")
    backboard_api_key: str = Field(default="")
    langsmith_api_key: str = Field(default="")

    # GitHub MCP
    github_mcp_image: str = Field(default="ghcr.io/github/github-mcp-server")
    github_mcp_timeout: float = Field(default=30.0)
    github_mcp_connect_timeout: float = Field(default=10.0)

    # Google Meet (future)
    google_meet_bot_email: str = Field(default="")

    # Zoom (future)
    zoom_client_id: str = Field(default="")
    zoom_client_secret: str = Field(default="")

    # Default repo for get_repo_context()
    default_repo_owner: str = Field(default="")
    default_repo_name: str = Field(default="")
    repo_context_max_issues: int = Field(default=10)
    repo_context_max_prs: int = Field(default=10)
    repo_context_max_commits: int = Field(default=20)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
