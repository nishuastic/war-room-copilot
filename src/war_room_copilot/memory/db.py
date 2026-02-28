"""SQLite persistence for call metadata, transcript, and decisions."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import aiosqlite

from ..models import Decision, TranscriptSegment

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_name TEXT NOT NULL,
    started_at REAL NOT NULL,
    ended_at REAL
);
CREATE TABLE IF NOT EXISTS transcript (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    speaker_id TEXT NOT NULL,
    text TEXT NOT NULL,
    timestamp REAL NOT NULL,
    is_passive INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    text TEXT NOT NULL,
    speaker_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    confidence REAL NOT NULL,
    context TEXT NOT NULL DEFAULT ''
);
"""


class IncidentDB:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_CREATE_TABLES)
        await self._conn.commit()

    def _db(self) -> aiosqlite.Connection:
        assert self._conn is not None, "DB not initialized — call initialize() first"
        return self._conn

    async def start_session(self, room_name: str) -> int:
        cur = await self._db().execute(
            "INSERT INTO sessions (room_name, started_at) VALUES (?, ?)",
            (room_name, time.time()),
        )
        await self._db().commit()
        assert cur.lastrowid is not None
        return cur.lastrowid

    async def end_session(self, session_id: int) -> None:
        await self._db().execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (time.time(), session_id),
        )
        await self._db().commit()

    async def add_segment(self, session_id: int, segment: TranscriptSegment) -> None:
        await self._db().execute(
            "INSERT INTO transcript (session_id, speaker_id, text, timestamp, is_passive) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                session_id,
                segment.speaker_id,
                segment.text,
                segment.timestamp,
                int(segment.is_passive),
            ),
        )
        await self._db().commit()

    async def add_decision(self, session_id: int, decision: Decision) -> None:
        await self._db().execute(
            "INSERT OR REPLACE INTO decisions "
            "(id, session_id, text, speaker_id, timestamp, confidence, context) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                decision.id,
                session_id,
                decision.text,
                decision.speaker_id,
                decision.timestamp,
                decision.confidence,
                decision.context,
            ),
        )
        await self._db().commit()

    async def get_decisions(self, session_id: int | None = None) -> list[Decision]:
        if session_id is not None:
            rows = await self._db().execute_fetchall(
                "SELECT * FROM decisions WHERE session_id = ? ORDER BY timestamp DESC",
                (session_id,),
            )
        else:
            rows = await self._db().execute_fetchall(
                "SELECT * FROM decisions ORDER BY timestamp DESC",
            )
        return [self._row_to_decision(r) for r in rows]

    async def search_decisions(self, query: str) -> list[Decision]:
        rows = await self._db().execute_fetchall(
            "SELECT * FROM decisions WHERE text LIKE ? OR context LIKE ? ORDER BY timestamp DESC",
            (f"%{query}%", f"%{query}%"),
        )
        return [self._row_to_decision(r) for r in rows]

    async def get_sessions(self) -> list[dict[str, Any]]:
        rows = await self._db().execute_fetchall(
            "SELECT * FROM sessions ORDER BY started_at DESC",
        )
        return [dict(r) for r in rows]

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @staticmethod
    def _row_to_decision(row: Any) -> Decision:
        return Decision(
            id=row["id"],
            text=row["text"],
            speaker_id=row["speaker_id"],
            timestamp=row["timestamp"],
            confidence=row["confidence"],
            context=row["context"],
        )
