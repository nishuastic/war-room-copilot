"""Tests for API routes using FastAPI TestClient with DB dependency override."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from src.war_room_copilot.api.deps import get_db
from src.war_room_copilot.api.main import app
from src.war_room_copilot.memory.db import IncidentDB
from src.war_room_copilot.models import TranscriptSegment


@pytest.fixture
async def client(test_db: IncidentDB):
    """AsyncClient with the DB dependency overridden to use the test DB."""

    async def _override() -> IncidentDB:
        return test_db

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestListSessions:
    async def test_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_with_session(self, client: AsyncClient, test_db: IncidentDB) -> None:
        await test_db.start_session("room-1")
        resp = await client.get("/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["room_name"] == "room-1"


class TestGetSession:
    async def test_404(self, client: AsyncClient) -> None:
        resp = await client.get("/sessions/999")
        assert resp.status_code == 404

    async def test_found(self, client: AsyncClient, test_db: IncidentDB) -> None:
        sid = await test_db.start_session("room-2")
        resp = await client.get(f"/sessions/{sid}")
        assert resp.status_code == 200
        assert resp.json()["room_name"] == "room-2"


class TestGetTranscript:
    async def test_empty(self, client: AsyncClient, test_db: IncidentDB) -> None:
        sid = await test_db.start_session("room-3")
        resp = await client.get(f"/sessions/{sid}/transcript")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_with_segments(self, client: AsyncClient, test_db: IncidentDB) -> None:
        sid = await test_db.start_session("room-4")
        seg = TranscriptSegment(speaker_id="alice", text="pods down", timestamp=time.time())
        await test_db.add_segment(sid, seg)
        resp = await client.get(f"/sessions/{sid}/transcript")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["text"] == "pods down"


class TestGetDecisions:
    async def test_empty(self, client: AsyncClient, test_db: IncidentDB) -> None:
        sid = await test_db.start_session("room-5")
        resp = await client.get(f"/sessions/{sid}/decisions")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetMetrics:
    async def test_404(self, client: AsyncClient) -> None:
        resp = await client.get("/sessions/999/metrics")
        assert resp.status_code == 404

    async def test_default_metrics(self, client: AsyncClient, test_db: IncidentDB) -> None:
        sid = await test_db.start_session("room-6")
        resp = await client.get(f"/sessions/{sid}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["llm_calls"] == 0
        assert "cost_usd" in data
