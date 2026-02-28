"""TTS configuration."""

from __future__ import annotations

from livekit.agents import tts
from livekit.plugins import openai as openai_plugin


def create_tts() -> tts.TTS:
    return openai_plugin.TTS(model="tts-1", voice="alloy")
