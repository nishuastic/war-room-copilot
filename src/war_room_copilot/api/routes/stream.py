"""SSE streaming routes for live transcript and agent trace."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ...memory.db import IncidentDB
from ..deps import get_db

router = APIRouter()


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


async def _sse_rows_with_partials(
    fetch_fn: Any,
    db: IncidentDB,
    session_id: int,
) -> AsyncGenerator[str, None]:
    """Emit named SSE events: 'final' for completed rows, 'partial' for in-progress text."""
    last_id = 0
    tick = 0
    while True:
        # Every tick: check for new final rows
        rows: list[dict[str, Any]] = await fetch_fn(session_id, last_id)
        for row in rows:
            last_id = int(row["id"])
            yield f"event: final\ndata: {json.dumps(row)}\n\n"

        # Every other tick (~400ms): emit current partials
        if tick % 2 == 0:
            partials = await db.get_partials(session_id)
            if partials:
                yield f"event: partial\ndata: {json.dumps(partials)}\n\n"

        tick += 1
        await asyncio.sleep(0.2)


@router.get("/sessions/latest/id")
async def latest_session_id(db: IncidentDB = Depends(get_db)) -> dict[str, Any]:
    sid = await db.get_latest_session_id()
    return {"session_id": sid}


@router.get("/sessions/{session_id}/stream")
async def stream_transcript(session_id: int, db: IncidentDB = Depends(get_db)) -> StreamingResponse:
    return StreamingResponse(
        _sse_rows_with_partials(db.get_transcript_since, db, session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions/{session_id}/trace")
async def stream_trace(session_id: int, db: IncidentDB = Depends(get_db)) -> StreamingResponse:
    return StreamingResponse(
        _sse_rows(db.get_trace_since, session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
