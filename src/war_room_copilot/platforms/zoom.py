"""Zoom platform — stub implementation."""

from __future__ import annotations

import logging

from war_room_copilot.platforms.base import load_agent_prompt, load_known_speakers

logger = logging.getLogger("war-room-copilot.platforms.zoom")


class ZoomPlatform:
    """Stub for Zoom integration.

    Future implementation would:
    1. Join meeting via Zoom Meeting Bot SDK
    2. Capture audio stream
    3. Run VAD → STT → LLM → TTS manually
    4. Play TTS audio back into meeting
    """

    def __init__(self, meeting_id: str) -> None:
        self._meeting_id = meeting_id
        self._prompt = load_agent_prompt()
        self._speakers = load_known_speakers()

    def run(self) -> None:
        logger.info("Zoom stub: would join meeting %s", self._meeting_id)
        logger.info("System prompt loaded (%d chars)", len(self._prompt))
        logger.info("Known speakers: %d", len(self._speakers))
        raise NotImplementedError(
            "Zoom platform is not yet implemented. "
            "See platforms/base.py for the MeetingPlatform protocol."
        )

    async def shutdown(self) -> None:
        pass
