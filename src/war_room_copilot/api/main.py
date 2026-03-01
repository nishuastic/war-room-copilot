"""FastAPI SSE endpoint for the War Room Copilot dashboard.

Streams transcript, findings, and decisions from the shared session
state as Server-Sent Events.  Started as a background task alongside
the LiveKit agent so both share the same process and state dict.

Events are emitted as structured JSON matching the frontend TypeScript
interfaces (TranscriptMessage, Finding, Decision, AgentTraceStep, etc.)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
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

# Pattern to parse legacy transcript lines: "[HH:MM:SS] Speaker: text"
_LEGACY_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s*(.+?):\s*(.+)$")


def set_state_ref(state: dict[str, Any]) -> None:
    """Point the API at the live session state dict."""
    global _state_ref  # noqa: PLW0603
    _state_ref = state


def _format_relative(epoch: float, start: float) -> str:
    """Format epoch as +MM:SS relative to session start."""
    delta = max(0, int(epoch - start))
    return f"+{delta // 60:02d}:{delta % 60:02d}"


def _speaker_name_to_id(name: str, speakers_list: list[dict[str, Any]]) -> int | str:
    """Map a speaker display name to its numeric ID, or 'ai' for the agent."""
    name_lower = name.lower()
    if any(kw in name_lower for kw in ("agent", "copilot", "ai", "war room")):
        return "ai"
    for s in speakers_list:
        if s["name"] == name:
            return s["id"]
    return 0


def _infer_message_type(text: str, speaker_id: int | str) -> str:
    """Infer transcript message type from content."""
    if speaker_id == "ai":
        text_lower = text.lower()
        if "contradiction" in text_lower:
            return "contradiction"
        if "decision" in text_lower:
            return "decision"
        return "ai"
    return "normal"


def _to_transcript_msg(
    entry: dict[str, Any], idx: int, start_epoch: float, speakers_list: list[dict[str, Any]]
) -> dict[str, Any]:
    """Convert a structured transcript entry to frontend TranscriptMessage format."""
    speaker_id = _speaker_name_to_id(entry["speaker"], speakers_list)
    text = entry["text"]
    return {
        "id": f"t{idx + 1}",
        "timestamp": _format_relative(entry.get("epoch", start_epoch), start_epoch),
        "speakerId": speaker_id,
        "text": text,
        "type": _infer_message_type(text, speaker_id),
    }


def _to_finding(entry: dict[str, Any], idx: int, start_epoch: float) -> dict[str, Any]:
    """Convert a structured finding to frontend Finding format."""
    return {
        "id": f"f{idx + 1}",
        "text": entry["text"],
        "source": entry.get("source", "code"),
        "timestamp": _format_relative(entry.get("epoch", start_epoch), start_epoch),
    }


def _to_decision(entry: dict[str, Any], idx: int, start_epoch: float) -> dict[str, Any]:
    """Convert a structured decision to frontend Decision format."""
    return {
        "id": f"d{idx + 1}",
        "number": idx + 1,
        "text": entry["text"],
        "speaker": entry.get("speaker", ""),
        "timestamp": _format_relative(entry.get("epoch", start_epoch), start_epoch),
    }


def _to_trace_step(entry: dict[str, Any], idx: int, start_epoch: float) -> dict[str, Any]:
    """Convert a graph trace entry to frontend AgentTraceStep format."""
    return {
        "id": f"s{idx + 1}",
        "skill": entry.get("node", "unknown"),
        "query": entry.get("query", ""),
        "duration": entry.get("duration", 0),
        "status": "completed",
        "timestamp": _format_relative(entry.get("epoch", start_epoch), start_epoch),
    }


def _to_timeline_event(entry: dict[str, Any], idx: int, start_epoch: float) -> dict[str, Any]:
    """Convert a timeline entry to frontend TimelineEvent format."""
    return {
        "id": f"e{idx + 1}",
        "type": entry.get("type", "transcript"),
        "description": entry.get("description", ""),
        "timestamp": _format_relative(entry.get("epoch", start_epoch), start_epoch),
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    """Serve the self-contained dashboard UI."""
    return DASHBOARD_HTML


@app.get("/events")
async def events() -> StreamingResponse:
    """SSE endpoint — streams structured events matching frontend TypeScript types."""

    async def stream() -> Any:
        last_transcript = 0
        last_findings = 0
        last_decisions = 0
        last_traces = 0
        last_timeline = 0
        last_orb_state = ""
        last_speakers_count = 0
        event_id = 0

        yield "retry: 3000\n\n"

        while True:
            try:
                start_epoch = _state_ref.get("session_start_epoch", 0)
                speakers_list = _state_ref.get("speakers_list", [])

                # Structured transcript
                structured = _state_ref.get("transcript_structured", [])
                for i, entry in enumerate(structured[last_transcript:], start=last_transcript):
                    event_id += 1
                    msg = _to_transcript_msg(entry, i, start_epoch, speakers_list)
                    payload = json.dumps({"type": "transcript", "data": msg})
                    yield f"id: {event_id}\ndata: {payload}\n\n"
                last_transcript = len(structured)

                # Structured findings
                findings_s = _state_ref.get("findings_structured", [])
                for i, entry in enumerate(findings_s[last_findings:], start=last_findings):
                    event_id += 1
                    finding = _to_finding(entry, i, start_epoch)
                    payload = json.dumps({"type": "finding", "data": finding})
                    yield f"id: {event_id}\ndata: {payload}\n\n"
                last_findings = len(findings_s)

                # Structured decisions
                decisions_s = _state_ref.get("decisions_structured", [])
                for i, entry in enumerate(decisions_s[last_decisions:], start=last_decisions):
                    event_id += 1
                    decision = _to_decision(entry, i, start_epoch)
                    payload = json.dumps({"type": "decision", "data": decision})
                    yield f"id: {event_id}\ndata: {payload}\n\n"
                last_decisions = len(decisions_s)

                # Graph traces
                graph_traces = _state_ref.get("graph_traces", [])
                for i, entry in enumerate(graph_traces[last_traces:], start=last_traces):
                    event_id += 1
                    trace = _to_trace_step(entry, i, start_epoch)
                    payload = json.dumps({"type": "graph_trace", "data": trace})
                    yield f"id: {event_id}\ndata: {payload}\n\n"
                last_traces = len(graph_traces)

                # Timeline events
                timeline = _state_ref.get("timeline", [])
                for i, entry in enumerate(timeline[last_timeline:], start=last_timeline):
                    event_id += 1
                    tl = _to_timeline_event(entry, i, start_epoch)
                    payload = json.dumps({"type": "timeline", "data": tl})
                    yield f"id: {event_id}\ndata: {payload}\n\n"
                last_timeline = len(timeline)

                # Orb state changes
                orb_state = _state_ref.get("orb_state", "idle")
                if orb_state != last_orb_state:
                    event_id += 1
                    payload = json.dumps({"type": "orb_state", "data": {"state": orb_state}})
                    yield f"id: {event_id}\ndata: {payload}\n\n"
                    last_orb_state = orb_state

                # New speakers
                current_speakers_count = len(speakers_list)
                if current_speakers_count > last_speakers_count:
                    for s in speakers_list[last_speakers_count:]:
                        event_id += 1
                        payload = json.dumps({"type": "speaker_update", "data": s})
                        yield f"id: {event_id}\ndata: {payload}\n\n"
                    last_speakers_count = current_speakers_count

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
    """Return a point-in-time snapshot of the session state.

    Returns structured data matching frontend TypeScript interfaces.
    """
    start_epoch = _state_ref.get("session_start_epoch", 0)
    speakers_list = _state_ref.get("speakers_list", [])
    structured = _state_ref.get("transcript_structured", [])
    findings_s = _state_ref.get("findings_structured", [])
    decisions_s = _state_ref.get("decisions_structured", [])
    traces = _state_ref.get("graph_traces", [])
    timeline = _state_ref.get("timeline", [])

    return {
        "transcript": [
            _to_transcript_msg(e, i, start_epoch, speakers_list) for i, e in enumerate(structured)
        ],
        "findings": [_to_finding(f, i, start_epoch) for i, f in enumerate(findings_s)],
        "decisions": [_to_decision(d, i, start_epoch) for i, d in enumerate(decisions_s)],
        "speakers": speakers_list,
        "graph_traces": [_to_trace_step(t, i, start_epoch) for i, t in enumerate(traces)],
        "timeline": [_to_timeline_event(t, i, start_epoch) for i, t in enumerate(timeline)],
        "orb_state": _state_ref.get("orb_state", "idle"),
    }
