"""Tests for FastAPI dashboard API — state snapshot and SSE streaming."""

from __future__ import annotations

from starlette.testclient import TestClient

from war_room_copilot.api.main import app, set_state_ref

# ── set_state_ref and /state ─────────────────────────────────────────────────


def test_state_snapshot_empty() -> None:
    """Empty state returns empty lists and dict."""
    set_state_ref({})
    client = TestClient(app)
    resp = client.get("/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"] == []
    assert data["findings"] == []
    assert data["decisions"] == []
    assert data["speakers"] == {}


def test_state_snapshot_with_data() -> None:
    """Populated state is returned correctly."""
    set_state_ref(
        {
            "transcript": ["10:00 Alice: alert fired"],
            "findings": ["DB latency spike"],
            "decisions": ["Roll back checkout"],
            "speakers": {"S0": "Alice"},
        }
    )
    client = TestClient(app)
    resp = client.get("/state")
    data = resp.json()
    assert data["transcript"] == ["10:00 Alice: alert fired"]
    assert data["findings"] == ["DB latency spike"]
    assert data["decisions"] == ["Roll back checkout"]
    assert data["speakers"] == {"S0": "Alice"}


def test_set_state_ref_updates_state() -> None:
    """set_state_ref changes what /state returns."""
    set_state_ref({"transcript": ["line1"]})
    client = TestClient(app)
    assert client.get("/state").json()["transcript"] == ["line1"]

    set_state_ref({"transcript": ["line2"]})
    assert client.get("/state").json()["transcript"] == ["line2"]


def test_state_includes_speakers() -> None:
    """Speakers dict is included in the /state response."""
    set_state_ref({"speakers": {"S0": "Alice", "S1": "Bob"}})
    client = TestClient(app)
    data = client.get("/state").json()
    assert data["speakers"]["S0"] == "Alice"
    assert data["speakers"]["S1"] == "Bob"
