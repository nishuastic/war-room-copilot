"""Thread/session management for Backboard conversations.

Maps user identities to Backboard thread IDs. Threads are created
on demand and cached in memory for the duration of the agent session.

Vendored from livekit/agents PR #4964.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger("livekit.plugins.backboard")


class SessionStore:
    """Manages user -> thread_id mappings for Backboard conversations."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://app.backboard.io/api",
        assistant_id: str,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._assistant_id = assistant_id
        self._cache: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None

    def set_assistant_id(self, assistant_id: str) -> None:
        self._assistant_id = assistant_id

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def _create_thread(self) -> str:
        client = self._get_client()
        resp = await client.post(
            f"{self._base_url}/assistants/{self._assistant_id}/threads",
            headers={
                "X-API-Key": self._api_key,
                "Content-Type": "application/json",
            },
            json={},
        )
        resp.raise_for_status()
        return str(resp.json()["thread_id"])

    async def get_or_create_thread(self, user_id: str) -> str:
        if user_id in self._cache:
            return self._cache[user_id]
        async with self._lock:
            if user_id in self._cache:
                return self._cache[user_id]
            thread_id = await self._create_thread()
            self._cache[user_id] = thread_id
            logger.info("Created Backboard thread %s for user %s", thread_id, user_id)
            return thread_id

    def set_thread(self, user_id: str, thread_id: str) -> None:
        self._cache[user_id] = thread_id

    def get_thread(self, user_id: str) -> str | None:
        return self._cache.get(user_id)

    def clear(self, user_id: str) -> None:
        self._cache.pop(user_id, None)

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
