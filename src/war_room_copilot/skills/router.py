"""Intent-based skill classification using a fast LLM."""

from __future__ import annotations

import asyncio
import json
import logging

from openai import AsyncOpenAI

from ..config import ROUTER_MODEL, ROUTER_TIMEOUT
from .models import Skill, SkillResult

logger = logging.getLogger("war-room-copilot")

_ROUTER_SYSTEM_PROMPT = """\
You are a skill classifier for a production incident war room AI assistant.

Given the recent conversation context and the user's message, \
classify the intent into exactly one skill:

- **debug**: Root cause analysis, asks "why" something broke, trace an error.
- **ideate**: Brainstorming, "what should we do", options or trade-offs.
- **investigate**: Proactively look something up — commits, code, files.
- **recall**: Past decisions, previous incidents, "what did we decide".
- **summarize**: Status update, recap, "where are we", "what do we know".
- **general**: Anything else — greetings, unclear intent, acknowledgements.

Respond with JSON only:
{"skill": "<skill>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>"}
"""


class SkillRouter:
    """Classifies user intent into a Skill using a fast/cheap LLM."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI()

    async def classify(self, context: str, user_message: str) -> SkillResult:
        """Classify the user's message into a skill.

        Uses a fast model with a short timeout.
        Falls back to GENERAL on any failure.
        """
        # Truncate context to last 2000 chars
        truncated = context[-2000:] if len(context) > 2000 else context
        user_content = f"Context:\n{truncated}\n\nUser message: {user_message}"

        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=ROUTER_MODEL,
                    messages=[
                        {"role": "system", "content": _ROUTER_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                    max_tokens=100,
                ),
                timeout=ROUTER_TIMEOUT,
            )

            raw = response.choices[0].message.content or "{}"
            data = json.loads(raw)

            skill = Skill(data["skill"].lower())
            confidence = max(0.0, min(1.0, float(data["confidence"])))
            reasoning = str(data.get("reasoning", ""))

            result = SkillResult(skill=skill, confidence=confidence, reasoning=reasoning)
            logger.info(
                "Skill route: %s (%.2f) — %s",
                result.skill.value,
                result.confidence,
                result.reasoning,
            )
            return result

        except asyncio.TimeoutError:
            logger.warning(
                "Skill router timed out after %.1fs — defaulting to GENERAL",
                ROUTER_TIMEOUT,
            )
            return SkillResult(
                skill=Skill.GENERAL,
                confidence=1.0,
                reasoning="Router timeout",
            )
        except Exception:
            logger.exception("Skill router error — defaulting to GENERAL")
            return SkillResult(
                skill=Skill.GENERAL,
                confidence=1.0,
                reasoning="Router error",
            )
