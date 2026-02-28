"""LLM provider factory — returns a LiveKit-compatible LLM instance."""

from __future__ import annotations

import logging
from typing import Any

from war_room_copilot.config import get_settings

logger = logging.getLogger("war-room-copilot.llm")

SUPPORTED_PROVIDERS = ("openai", "anthropic", "google")

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
    "google": "gemini-2.0-flash",
}


def create_llm() -> Any:
    """Build an LLM instance based on config (LLM_PROVIDER, LLM_MODEL).

    Returns a LiveKit plugin LLM object.  All LiveKit LLM plugins conform
    to the same interface, so callers don't need to know which provider
    is in use.
    """
    cfg = get_settings()
    provider = cfg.llm_provider.lower()
    model = cfg.llm_model or DEFAULT_MODELS.get(provider, "")

    if provider == "openai":
        from livekit.plugins import openai

        logger.info("Using OpenAI LLM: %s", model)
        return openai.LLM(model=model)

    if provider == "anthropic":
        from livekit.plugins import anthropic  # type: ignore[attr-defined]

        logger.info("Using Anthropic LLM: %s", model)
        return anthropic.LLM(model=model)

    if provider == "google":
        from livekit.plugins import google  # type: ignore[attr-defined]

        logger.info("Using Google LLM: %s", model)
        return google.LLM(model=model)

    raise ValueError(
        f"Unknown LLM provider: {provider!r}. Supported: {', '.join(SUPPORTED_PROVIDERS)}"
    )
