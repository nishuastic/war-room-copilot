"""Main orchestration — manages transcript buffer, contradiction checker, dashboard events."""

from __future__ import annotations

import asyncio
import logging
import time

from war_room_copilot.config import settings
from war_room_copilot.memory.short_term import TranscriptBuffer
from war_room_copilot.models import (
    DashboardEvent,
    EventType,
    InterjectionDecision,
    TranscriptChunk,
)
from war_room_copilot.skills.contradict import ContradictSkill

logger = logging.getLogger("war-room-copilot.pipeline")


class Pipeline:
    """Runs alongside the AgentSession to handle passive monitoring."""

    def __init__(self) -> None:
        self.transcript_buffer = TranscriptBuffer()
        self.contradict_skill = ContradictSkill()
        self._event_subscribers: list[asyncio.Queue[DashboardEvent]] = []
        self._running = False
        self._last_speech_time = time.time()

    def subscribe(self) -> asyncio.Queue[DashboardEvent]:
        q: asyncio.Queue[DashboardEvent] = asyncio.Queue()
        self._event_subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[DashboardEvent]) -> None:
        self._event_subscribers.remove(q)

    async def broadcast(self, event: DashboardEvent) -> None:
        for q in self._event_subscribers:
            await q.put(event)

    def add_transcript(self, chunk: TranscriptChunk) -> None:
        self.transcript_buffer.add(chunk)
        self._last_speech_time = time.time()
        asyncio.create_task(
            self.broadcast(DashboardEvent(type=EventType.TRANSCRIPT, data=chunk.model_dump()))
        )

    async def start_contradiction_loop(self) -> None:
        """Periodically check transcript for contradictions."""
        self._running = True
        while self._running:
            await asyncio.sleep(settings.contradict_check_interval_seconds)
            window = self.transcript_buffer.get_window()
            if not window.chunks:
                continue

            silence = time.time() - self._last_speech_time
            decision = await self.contradict_skill.analyze(window)
            await self._handle_interjection(decision, silence)

    async def _handle_interjection(
        self, decision: InterjectionDecision, silence_seconds: float
    ) -> None:
        if not decision.should_interject:
            return

        if decision.confidence >= settings.interjection_confidence_speak:
            if silence_seconds >= settings.silence_threshold_seconds:
                await self.broadcast(
                    DashboardEvent(
                        type=EventType.INTERJECTION,
                        data={"speak": True, **decision.model_dump()},
                    )
                )
                logger.info("INTERJECTION (spoken): %s", decision.content)
            else:
                # Wait for silence
                await self.broadcast(
                    DashboardEvent(
                        type=EventType.INTERJECTION,
                        data={"speak": False, "queued": True, **decision.model_dump()},
                    )
                )
        elif decision.confidence >= settings.interjection_confidence_dashboard:
            await self.broadcast(
                DashboardEvent(
                    type=EventType.INTERJECTION,
                    data={"speak": False, **decision.model_dump()},
                )
            )
            logger.info("INTERJECTION (dashboard only): %s", decision.content)

    def stop(self) -> None:
        self._running = False
