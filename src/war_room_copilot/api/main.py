"""FastAPI SSE endpoint for the War Room Copilot dashboard.

Streams transcript, findings, and decisions from the shared session
state as Server-Sent Events.  Started as a background task alongside
the LiveKit agent so both share the same process and state dict.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

logger = logging.getLogger("war-room-copilot.api")

app = FastAPI(title="War Room Copilot Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Populated by livekit.py via set_state_ref() at startup.
_state_ref: dict[str, Any] = {}


def set_state_ref(state: dict[str, Any]) -> None:
    """Point the API at the live session state dict."""
    global _state_ref  # noqa: PLW0603
    _state_ref = state


@app.get("/events")
async def events() -> StreamingResponse:
    """SSE endpoint — streams transcript/finding/decision events."""

    async def stream() -> Any:
        last_transcript = 0
        last_findings = 0
        last_decisions = 0

        while True:
            transcript = _state_ref.get("transcript", [])
            findings = _state_ref.get("findings", [])
            decisions = _state_ref.get("decisions", [])

            for line in transcript[last_transcript:]:
                payload = json.dumps({"type": "transcript", "data": line})
                yield f"data: {payload}\n\n"
            last_transcript = len(transcript)

            for finding in findings[last_findings:]:
                payload = json.dumps({"type": "finding", "data": finding})
                yield f"data: {payload}\n\n"
            last_findings = len(findings)

            for decision in decisions[last_decisions:]:
                payload = json.dumps({"type": "decision", "data": decision})
                yield f"data: {payload}\n\n"
            last_decisions = len(decisions)

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
    }
