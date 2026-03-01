"""Standalone demo server — runs the dashboard API with a scripted scenario.

Usage:
    python -m war_room_copilot.api.demo_server

Starts uvicorn on port 8000 with the FastAPI app and feeds it a timed
incident scenario.  No LiveKit, no MCP, no API keys required.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from war_room_copilot.api.demo_scenario import run_demo_scenario
from war_room_copilot.api.main import app, set_state_ref

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("war-room-copilot.demo")

# Shared state dict — same structure as _session_state in livekit.py
_demo_state: dict = {
    "transcript": [],
    "transcript_structured": [],
    "findings": [],
    "findings_structured": [],
    "decisions": [],
    "decisions_structured": [],
    "speakers": {},
    "speakers_list": [],
    "messages": [],
    "graph_traces": [],
    "timeline": [],
    "orb_state": "idle",
    "session_start_epoch": 0,
}


@asynccontextmanager
async def _demo_lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Lifespan handler that starts the demo scenario on server boot."""
    set_state_ref(_demo_state)
    task = asyncio.create_task(run_demo_scenario(_demo_state))
    logger.info("Demo mode active — scenario streaming to http://localhost:8000/events")
    yield
    task.cancel()


# Attach lifespan to the existing app
app.router.lifespan_context = _demo_lifespan


def main() -> None:
    logger.info("Starting War Room Copilot demo server on port 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
