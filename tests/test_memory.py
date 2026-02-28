"""Tests for memory subsystem: short-term memory, SQLite DB, and models."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest

from src.war_room_copilot.memory.db import IncidentDB
from src.war_room_copilot.memory.short_term import ShortTermMemory
from src.war_room_copilot.models import Decision, TranscriptSegment


# --- TranscriptSegment & Decision model tests ---


def _segment(speaker: str = "S1", text: str = "hello", ts: float = 0.0) -> TranscriptSegment:
    return TranscriptSegment(speaker_id=speaker, text=text, timestamp=ts or time.time())


def _decision(text: str = "Roll back checkout") -> Decision:
    return Decision(
        id=str(uuid.uuid4()),
        text=text,
        speaker_id="alice",
        timestamp=time.time(),
        context="discussing rollback",
        confidence=0.9,
    )


class TestDecisionModel:
    def test_create(self) -> None:
        d = _decision()
        assert d.text == "Roll back checkout"
        assert d.confidence == 0.9
        assert d.speaker_id == "alice"

    def test_validation(self) -> None:
        with pytest.raises(Exception):
            Decision(id="x", text="t", speaker_id="s", timestamp=0, context="c", confidence="bad")  # type: ignore[arg-type]


# --- ShortTermMemory tests ---


class TestShortTermMemory:
    def test_add_and_get_recent(self) -> None:
        mem = ShortTermMemory(max_segments=10)
        s1 = _segment(text="first")
        s2 = _segment(text="second")
        mem.add(s1)
        mem.add(s2)
        assert len(mem) == 2
        assert mem.get_recent() == [s1, s2]
        assert mem.get_recent(1) == [s2]

    def test_sliding_window_eviction(self) -> None:
        mem = ShortTermMemory(max_segments=3)
        for i in range(5):
            mem.add(_segment(text=f"msg-{i}"))
        assert len(mem) == 3
        texts = [s.text for s in mem.get_recent()]
        assert texts == ["msg-2", "msg-3", "msg-4"]

    def test_format_context(self) -> None:
        mem = ShortTermMemory(max_segments=10)
        mem.add(_segment(speaker="alice", text="the pod is crashing"))
        mem.add(TranscriptSegment(speaker_id="bob", text="checking logs", timestamp=1.0, is_passive=True))
        ctx = mem.format_context()
        assert "[alice] the pod is crashing" in ctx
        assert "[PASSIVE] [bob] checking logs" in ctx

    def test_search(self) -> None:
        mem = ShortTermMemory(max_segments=10)
        mem.add(_segment(text="pod is restarting"))
        mem.add(_segment(text="checking the dashboard"))
        mem.add(_segment(text="pod OOMKilled"))
        results = mem.search("pod")
        assert len(results) == 2

    def test_clear(self) -> None:
        mem = ShortTermMemory(max_segments=10)
        mem.add(_segment(text="something"))
        mem.clear()
        assert len(mem) == 0
        assert mem.get_recent() == []


# --- IncidentDB tests ---


class TestIncidentDB:
    @pytest.fixture
    async def db(self, tmp_path: Path) -> IncidentDB:
        db = IncidentDB(tmp_path / "test.db")
        await db.initialize()
        yield db  # type: ignore[misc]
        await db.close()

    async def test_start_session(self, db: IncidentDB) -> None:
        sid = await db.start_session("test-room")
        assert sid >= 1
        sessions = await db.get_sessions()
        assert len(sessions) == 1
        assert sessions[0]["room_name"] == "test-room"

    async def test_add_segment(self, db: IncidentDB) -> None:
        sid = await db.start_session("room-1")
        seg = _segment(speaker="alice", text="checking pods")
        await db.add_segment(sid, seg)
        # No direct get_segments, but verifies no errors

    async def test_add_and_get_decisions(self, db: IncidentDB) -> None:
        sid = await db.start_session("room-1")
        d = _decision("Roll back checkout service")
        await db.add_decision(sid, d)
        decisions = await db.get_decisions(sid)
        assert len(decisions) == 1
        assert decisions[0].text == "Roll back checkout service"

    async def test_get_all_decisions(self, db: IncidentDB) -> None:
        sid1 = await db.start_session("room-1")
        sid2 = await db.start_session("room-2")
        await db.add_decision(sid1, _decision("Decision A"))
        await db.add_decision(sid2, _decision("Decision B"))
        all_decisions = await db.get_decisions(None)
        assert len(all_decisions) == 2

    async def test_search_decisions(self, db: IncidentDB) -> None:
        sid = await db.start_session("room-1")
        await db.add_decision(sid, _decision("Roll back checkout"))
        await db.add_decision(sid, _decision("Scale up Redis"))
        results = await db.search_decisions("checkout")
        assert len(results) == 1
        assert "checkout" in results[0].text.lower()

    async def test_end_session(self, db: IncidentDB) -> None:
        sid = await db.start_session("room-1")
        await db.end_session(sid)
        sessions = await db.get_sessions()
        assert sessions[0]["ended_at"] is not None
