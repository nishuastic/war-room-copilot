"""TTS provider factory — returns a LiveKit-compatible TTS instance."""

from __future__ import annotations

import logging
from typing import Any

from war_room_copilot.config import get_settings

logger = logging.getLogger("war-room-copilot.tts")

SUPPORTED_TTS_PROVIDERS = ("openai", "elevenlabs", "google")

DEFAULT_TTS_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini-tts",
    "elevenlabs": "eleven_turbo_v2_5",
    "google": "default",
}


def create_tts() -> Any:
    """Build a TTS instance based on config (TTS_PROVIDER, TTS_MODEL).

    Returns a LiveKit plugin TTS object.  All LiveKit TTS plugins conform
    to the same interface, so callers don't need to know which provider
    is in use.
    """
    cfg = get_settings()
    provider = cfg.tts_provider.lower()
    model = cfg.tts_model or DEFAULT_TTS_MODELS.get(provider, "")

    if provider == "openai":
        from livekit.plugins import openai

        logger.info("Using OpenAI TTS: %s", model)
        return openai.TTS(model=model, voice="ash")

    if provider == "elevenlabs":
        from livekit.plugins import elevenlabs

        logger.info("Using ElevenLabs TTS: %s", model)
        return elevenlabs.TTS(model=model)

    if provider == "google":
        from livekit.plugins import google  # type: ignore[attr-defined]

        logger.info("Using Google TTS: %s", model)
        return google.TTS(model=model)

    raise ValueError(
        f"Unknown TTS provider: {provider!r}. Supported: {', '.join(SUPPORTED_TTS_PROVIDERS)}"
    )
