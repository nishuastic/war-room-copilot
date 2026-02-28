"""WebSocket endpoint — streams transcript, traces, and events to the dashboard."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from war_room_copilot.api.main import pipeline

logger = logging.getLogger("war-room-copilot.ws")
ws_router = APIRouter()


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = pipeline.subscribe()
    logger.info("Dashboard client connected")

    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        logger.info("Dashboard client disconnected")
    except asyncio.CancelledError:
        pass
    finally:
        pipeline.unsubscribe(queue)
