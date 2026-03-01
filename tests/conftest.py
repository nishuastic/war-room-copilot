"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.war_room_copilot.memory.db import IncidentDB


@pytest.fixture
async def test_db(tmp_path: Path) -> IncidentDB:
    """Ephemeral SQLite database in a temp directory."""
    db = IncidentDB(tmp_path / "test.db")
    await db.initialize()
    yield db  # type: ignore[misc]
    await db.close()


@pytest.fixture
def mock_openai() -> AsyncMock:
    """AsyncMock that can stand in for ``AsyncOpenAI``."""
    return AsyncMock()
