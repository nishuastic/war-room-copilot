"""FastAPI server — read-only observability layer over the SQLite incident DB."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import DB_FILE
from ..memory.db import IncidentDB
from .routes import sessions as sessions_routes
from .routes import stream as stream_routes

logger = logging.getLogger("war-room-api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    db = IncidentDB(DB_FILE)
    await db.initialize()
    sessions_routes.set_db(db)
    stream_routes.set_db(db)
    logger.info("DB opened: %s", DB_FILE)
    yield
    await db.close()


app = FastAPI(title="War Room Copilot API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_routes.router)
app.include_router(stream_routes.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.war_room_copilot.api.main:app", host="0.0.0.0", port=8000, reload=True)
