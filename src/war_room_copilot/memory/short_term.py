"""Sliding window transcript buffer with speaker labels."""

from __future__ import annotations

import time

from war_room_copilot.config import settings
from war_room_copilot.models import TranscriptChunk, TranscriptWindow


class TranscriptBuffer:
    def __init__(self, window_seconds: float | None = None) -> None:
        self._chunks: list[TranscriptChunk] = []
        self._window = window_seconds or settings.transcript_window_seconds

    def add(self, chunk: TranscriptChunk) -> None:
        self._chunks.append(chunk)
        self._prune()

    def _prune(self) -> None:
        cutoff = time.time() - self._window
        self._chunks = [c for c in self._chunks if c.timestamp.timestamp() > cutoff]

    def get_window(self) -> TranscriptWindow:
        self._prune()
        return TranscriptWindow(chunks=list(self._chunks))

    def clear(self) -> None:
        self._chunks.clear()
