"""Tests for FastAPI dashboard API — state snapshot and SSE streaming."""

from __future__ import annotations

import time

from starlette.testclient import TestClient

from war_room_copilot.api.main import app, set_state_ref

# ── set_state_ref and /state ─────────────────────────────────────────────────


def test_state_snapshot_empty() -> None:
    """Empty state returns empty lists."""
    set_state_ref({})
    client = TestClient(app)
    resp = client.get("/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"] == []
    assert data["findings"] == []
    assert data["decisions"] == []
    assert data["speakers"] == []


def test_state_snapshot_with_data() -> None:
    """Populated state is returned as structured objects."""
    now = time.time()
    set_state_ref(
        {
            "session_start_epoch": now - 60,
            "transcript_structured": [
                {"speaker": "Alice", "text": "alert fired", "timestamp": "10:00:00", "epoch": now},
            ],
            "findings_structured": [
                {"text": "DB latency spike", "source": "metrics", "epoch": now},
            ],
            "decisions_structured": [
                {"text": "Roll back checkout", "speaker": "Alice", "epoch": now},
            ],
            "speakers_list": [
                {"id": 1, "name": "Alice", "role": "", "colorVar": "--speaker-1"},
            ],
            "graph_traces": [],
            "timeline": [],
        }
    )
    client = TestClient(app)
    resp = client.get("/state")
    data = resp.json()
    assert len(data["transcript"]) == 1
    assert data["transcript"][0]["text"] == "alert fired"
    assert data["transcript"][0]["speakerId"] == 1
    assert len(data["findings"]) == 1
    assert data["findings"][0]["source"] == "metrics"
    assert len(data["decisions"]) == 1
    assert data["decisions"][0]["speaker"] == "Alice"
    assert len(data["speakers"]) == 1
    assert data["speakers"][0]["name"] == "Alice"


def test_set_state_ref_updates_state() -> None:
    """set_state_ref changes what /state returns."""
    now = time.time()
    set_state_ref(
        {
            "session_start_epoch": now,
            "transcript_structured": [
                {"speaker": "A", "text": "line1", "timestamp": "00:00", "epoch": now},
            ],
        }
    )
    client = TestClient(app)
    assert client.get("/state").json()["transcript"][0]["text"] == "line1"

    set_state_ref(
        {
            "session_start_epoch": now,
            "transcript_structured": [
                {"speaker": "A", "text": "line2", "timestamp": "00:00", "epoch": now},
            ],
        }
    )
    assert client.get("/state").json()["transcript"][0]["text"] == "line2"


def test_state_includes_speakers() -> None:
    """Speakers list is included in the /state response."""
    set_state_ref(
        {
            "speakers_list": [
                {"id": 1, "name": "Alice", "role": "", "colorVar": "--speaker-1"},
                {"id": 2, "name": "Bob", "role": "SRE", "colorVar": "--speaker-2"},
            ],
        }
    )
    client = TestClient(app)
    data = client.get("/state").json()
    assert len(data["speakers"]) == 2
    assert data["speakers"][0]["name"] == "Alice"
    assert data["speakers"][1]["name"] == "Bob"
