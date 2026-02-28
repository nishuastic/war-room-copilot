"""REST API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from war_room_copilot.api.main import pipeline
from war_room_copilot.models import IncidentSummary

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/transcript")
async def get_transcript() -> dict[str, Any]:
    window = pipeline.transcript_buffer.get_window()
    return {"chunks": [c.model_dump() for c in window.chunks]}


@router.get("/decisions")
async def get_decisions() -> dict[str, Any]:
    # Will be populated when DecisionTracker is wired in
    return {"decisions": []}


@router.get("/metrics")
async def get_metrics() -> dict[str, Any]:
    return {
        "total_chunks": len(pipeline.transcript_buffer.get_window().chunks),
        "subscribers": len(pipeline._event_subscribers),
    }


@router.post("/summary")
async def generate_summary() -> IncidentSummary:
    """Generate an incident summary from the current conversation."""
    return IncidentSummary(title="Incident Summary", timeline=[], decisions=[], action_items=[])
