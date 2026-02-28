"""SSE streaming routes for live transcript and agent trace."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ...memory.db import IncidentDB

router = APIRouter()
_db: IncidentDB | None = None


def set_db(db: IncidentDB) -> None:
    global _db
    _db = db


def _get_db() -> IncidentDB:
    assert _db is not None, "DB not set"
    return _db


async def _sse_rows(
    fetch_fn: Any,
    session_id: int,
) -> AsyncGenerator[str, None]:
    last_id = 0
    while True:
        rows: list[dict[str, Any]] = await fetch_fn(session_id, last_id)
        for row in rows:
            last_id = int(row["id"])
            yield f"data: {json.dumps(row)}\n\n"
        await asyncio.sleep(0.5)


@router.get("/sessions/latest/id")
async def latest_session_id() -> dict[str, Any]:
    sid = await _get_db().get_latest_session_id()
    return {"session_id": sid}


@router.get("/sessions/{session_id}/stream")
async def stream_transcript(session_id: int) -> StreamingResponse:
    return StreamingResponse(
        _sse_rows(_get_db().get_transcript_since, session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions/{session_id}/trace")
async def stream_trace(session_id: int) -> StreamingResponse:
    return StreamingResponse(
        _sse_rows(_get_db().get_trace_since, session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
