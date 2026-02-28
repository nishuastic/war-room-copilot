"""STT configuration — abstracts provider switching."""

from __future__ import annotations

from livekit.agents import stt

from war_room_copilot.config import settings


def create_stt() -> stt.STT:
    """Create STT provider. Uses Speechmatics if key is set, otherwise OpenAI Whisper."""
    if settings.speechmatics_api_key:
        from livekit.plugins import speechmatics

        return speechmatics.STT(
            language="en",
            model="enhanced",
            enable_partials=True,
            enable_entities=True,
        )

    from livekit.plugins import openai as openai_plugin

    return openai_plugin.STT(model="whisper-1")
