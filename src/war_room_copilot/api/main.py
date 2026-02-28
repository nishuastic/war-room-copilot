"""FastAPI application — REST + WebSocket for the dashboard."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from war_room_copilot.api.routes import router
from war_room_copilot.api.ws import ws_router
from war_room_copilot.core.pipeline import Pipeline

pipeline = Pipeline()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    import asyncio

    task = asyncio.create_task(pipeline.start_contradiction_loop())
    yield
    pipeline.stop()
    task.cancel()


app = FastAPI(title="War Room Copilot", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(ws_router)
