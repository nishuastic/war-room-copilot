"""REST routes for session, transcript, and decision data."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ...memory.db import IncidentDB

router = APIRouter()
_db: IncidentDB | None = None


def set_db(db: IncidentDB) -> None:
    global _db
    _db = db


def _get_db() -> IncidentDB:
    assert _db is not None, "DB not set"
    return _db


@router.get("/sessions")
async def list_sessions() -> list[dict[str, Any]]:
    return await _get_db().get_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: int) -> dict[str, Any]:
    session = await _get_db().get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/sessions/{session_id}/transcript")
async def get_transcript(session_id: int) -> list[dict[str, Any]]:
    return await _get_db().get_transcript(session_id)


@router.get("/sessions/{session_id}/decisions")
async def get_decisions(session_id: int) -> list[dict[str, Any]]:
    decisions = await _get_db().get_decisions(session_id)
    return [d.model_dump() for d in decisions]
