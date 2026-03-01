"""Tests for skills.router — intent classification."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.war_room_copilot.skills.models import Skill


def _mock_response(skill: str, confidence: float, addressed: bool = True) -> MagicMock:
    """Build a mock OpenAI chat completion response."""
    payload = {
        "skill": skill,
        "confidence": confidence,
        "reasoning": "test",
        "addressed_to_assistant": addressed,
    }
    msg = MagicMock()
    msg.content = json.dumps(payload)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_router() -> "SkillRouter":
    """Create a SkillRouter with a mocked OpenAI client."""
    with patch("src.war_room_copilot.skills.router.AsyncOpenAI"):
        from src.war_room_copilot.skills.router import SkillRouter

        router = SkillRouter()
    return router


class TestSkillRouter:
    async def test_classify_investigate(self) -> None:
        router = _make_router()
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = _mock_response("investigate", 0.95)
        router._client = mock_client

        result = await router.classify("some context", "Sam check the logs")
        assert result.skill == Skill.INVESTIGATE
        assert result.confidence == 0.95

    async def test_classify_debug(self) -> None:
        router = _make_router()
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = _mock_response("debug", 0.9)
        router._client = mock_client

        result = await router.classify("context", "Why is the API returning 500s?")
        assert result.skill == Skill.DEBUG

    async def test_classify_general(self) -> None:
        router = _make_router()
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = _mock_response("general", 0.8)
        router._client = mock_client

        result = await router.classify("context", "Hey Sam")
        assert result.skill == Skill.GENERAL

    async def test_not_addressed_zero_confidence(self) -> None:
        router = _make_router()
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = _mock_response(
            "debug", 0.9, addressed=False
        )
        router._client = mock_client

        result = await router.classify("context", "Sam broke the deploy")
        assert result.confidence == 0.0

    async def test_timeout_fallback(self) -> None:
        router = _make_router()
        mock_client = AsyncMock()

        async def _slow(*args: object, **kwargs: object) -> None:
            await asyncio.sleep(10)

        mock_client.chat.completions.create.side_effect = _slow
        router._client = mock_client

        with patch("src.war_room_copilot.skills.router.ROUTER_TIMEOUT", 0.01):
            result = await router.classify("context", "Sam check logs")

        assert result.skill == Skill.GENERAL
        assert "timeout" in result.reasoning.lower()
