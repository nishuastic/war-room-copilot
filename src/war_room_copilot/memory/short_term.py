"""Short-term memory: sliding window of transcript segments."""

from __future__ import annotations

from collections import deque

from ..models import TranscriptSegment


class ShortTermMemory:
    def __init__(self, max_segments: int) -> None:
        self._segments: deque[TranscriptSegment] = deque(maxlen=max_segments)

    def add(self, segment: TranscriptSegment) -> None:
        self._segments.append(segment)

    def get_recent(self, n: int | None = None) -> list[TranscriptSegment]:
        if n is None:
            return list(self._segments)
        return list(self._segments)[-n:]

    def format_context(self) -> str:
        lines: list[str] = []
        for seg in self._segments:
            prefix = "[PASSIVE] " if seg.is_passive else ""
            lines.append(f"{prefix}[{seg.speaker_id}] {seg.text}")
        return "\n".join(lines)

    def search(self, query: str) -> list[TranscriptSegment]:
        q = query.lower()
        return [s for s in self._segments if q in s.text.lower()]

    def clear(self) -> None:
        self._segments.clear()

    def __len__(self) -> int:
        return len(self._segments)
