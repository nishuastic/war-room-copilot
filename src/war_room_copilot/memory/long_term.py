"""Backboard.io persistent memory for cross-session recall."""

from __future__ import annotations

import logging

import httpx

from war_room_copilot.config import settings
from war_room_copilot.models import MemoryEntry

logger = logging.getLogger("war-room-copilot.memory")


class LongTermMemory:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.backboard_base_url,
            headers={"Authorization": f"Bearer {settings.backboard_api_key}"},
            timeout=10.0,
        )
        self._local_cache: dict[str, MemoryEntry] = {}

    async def store(self, entry: MemoryEntry) -> None:
        self._local_cache[entry.key] = entry
        if not settings.backboard_api_key:
            logger.debug("Backboard not configured, using local cache only")
            return
        try:
            await self._client.post(
                "/v1/memories",
                json={"key": entry.key, "value": entry.value, "metadata": {"source": entry.source}},
            )
        except httpx.HTTPError:
            logger.warning("Failed to store memory to Backboard", exc_info=True)

    async def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        if not settings.backboard_api_key:
            # Fallback: simple substring match on local cache
            return [e for e in self._local_cache.values() if query.lower() in e.value.lower()][
                :limit
            ]
        try:
            resp = await self._client.post(
                "/v1/memories/search",
                json={"query": query, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                MemoryEntry(
                    key=m["key"],
                    value=m["value"],
                    source=m.get("metadata", {}).get("source", "backboard"),
                )
                for m in data.get("results", [])
            ]
        except httpx.HTTPError:
            logger.warning("Failed to recall from Backboard", exc_info=True)
            return []

    async def close(self) -> None:
        await self._client.aclose()
