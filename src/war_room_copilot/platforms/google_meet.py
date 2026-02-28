"""Google Meet platform — stub implementation."""

from __future__ import annotations

import logging

from war_room_copilot.platforms.base import load_agent_prompt, load_known_speakers

logger = logging.getLogger("war-room-copilot.platforms.google_meet")


class GoogleMeetPlatform:
    """Stub for Google Meet integration.

    Future implementation would:
    1. Join meeting via Meet bot API or browser automation
    2. Capture audio stream
    3. Run VAD → STT → LLM → TTS manually
    4. Play TTS audio back into meeting
    """

    def __init__(self, meeting_url: str) -> None:
        self._meeting_url = meeting_url
        self._prompt = load_agent_prompt()
        self._speakers = load_known_speakers()

    def run(self) -> None:
        logger.info("Google Meet stub: would join %s", self._meeting_url)
        logger.info("System prompt loaded (%d chars)", len(self._prompt))
        logger.info("Known speakers: %d", len(self._speakers))
        raise NotImplementedError(
            "Google Meet platform is not yet implemented. "
            "See platforms/base.py for the MeetingPlatform protocol."
        )

    async def shutdown(self) -> None:
        pass
