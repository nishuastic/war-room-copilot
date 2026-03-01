"""FastAPI dependencies shared across route modules."""

from __future__ import annotations

from fastapi import Request

from ..memory.db import IncidentDB


async def get_db(request: Request) -> IncidentDB:
    """Return the IncidentDB instance stored on ``app.state``."""
    return request.app.state.db  # type: ignore[no-any-return]
