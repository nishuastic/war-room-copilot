"""FastAPI SSE endpoint for the War Room Copilot dashboard.

Streams transcript, findings, and decisions from the shared session
state as Server-Sent Events.  Started as a background task alongside
the LiveKit agent so both share the same process and state dict.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.responses import StreamingResponse

from war_room_copilot.api.dashboard import DASHBOARD_HTML

logger = logging.getLogger("war-room-copilot.api")

app = FastAPI(title="War Room Copilot Dashboard API")

# Allow configuration via env var; defaults to localhost origins only.
_allowed_origins = os.environ.get(
    "DASHBOARD_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Populated by livekit.py via set_state_ref() at startup.
_state_ref: dict[str, Any] = {}


def set_state_ref(state: dict[str, Any]) -> None:
    """Point the API at the live session state dict."""
    global _state_ref  # noqa: PLW0603
    _state_ref = state


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    """Serve the self-contained dashboard UI."""
    return DASHBOARD_HTML


@app.get("/events")
async def events() -> StreamingResponse:
    """SSE endpoint — streams transcript/finding/decision events."""

    async def stream() -> Any:
        last_transcript = 0
        last_findings = 0
        last_decisions = 0
        last_traces = 0
        event_id = 0

        yield "retry: 3000\n\n"

        while True:
            try:
                transcript = _state_ref.get("transcript", [])
                findings = _state_ref.get("findings", [])
                decisions = _state_ref.get("decisions", [])
                graph_traces = _state_ref.get("graph_traces", [])

                for line in transcript[last_transcript:]:
                    event_id += 1
                    payload = json.dumps({"type": "transcript", "data": line})
                    yield f"id: {event_id}\ndata: {payload}\n\n"
                last_transcript = len(transcript)

                for finding in findings[last_findings:]:
                    event_id += 1
                    payload = json.dumps({"type": "finding", "data": finding})
                    yield f"id: {event_id}\ndata: {payload}\n\n"
                last_findings = len(findings)

                for decision in decisions[last_decisions:]:
                    event_id += 1
                    payload = json.dumps({"type": "decision", "data": decision})
                    yield f"id: {event_id}\ndata: {payload}\n\n"
                last_decisions = len(decisions)

                for trace in graph_traces[last_traces:]:
                    event_id += 1
                    payload = json.dumps({"type": "graph_trace", "data": trace})
                    yield f"id: {event_id}\ndata: {payload}\n\n"
                last_traces = len(graph_traces)
            except Exception as exc:
                logger.error(
                    "SSE stream error (%s): %s",
                    type(exc).__name__,
                    exc,
                )
                err_payload = json.dumps(
                    {
                        "type": "error",
                        "data": f"{type(exc).__name__}: {exc}",
                    }
                )
                event_id += 1
                yield f"id: {event_id}\ndata: {err_payload}\n\n"

            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/state")
async def state_snapshot() -> dict[str, Any]:
    """Return a point-in-time snapshot of the session state."""
    return {
        "transcript": _state_ref.get("transcript", []),
        "findings": _state_ref.get("findings", []),
        "decisions": _state_ref.get("decisions", []),
        "speakers": _state_ref.get("speakers", {}),
        "graph_traces": _state_ref.get("graph_traces", []),
    }
