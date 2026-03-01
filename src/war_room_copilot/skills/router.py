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
classify the intent into EXACTLY one of these six skills. \
You MUST pick from this list — no other values are allowed:

- **debug**: Root cause analysis, "why did this break", trace errors, \
find the cause. E.g. "why is the API returning 500s?", "what caused the spike?"
- **ideate**: Brainstorming solutions, "what should we do", weighing options, \
trade-offs, mitigation strategies. E.g. "should we rollback or hotfix?"
- **investigate**: Proactively look something up in code, commits, PRs, or files. \
E.g. "check the last deploy", "what changed in the auth service?", "look at the logs"
- **recall**: Asking about past decisions, previous incidents, history. \
E.g. "what did we decide last time?", "have we seen this before?"
- **summarize**: Status updates, recaps, catch-ups, "what's going on", \
"where are we", gathering context. E.g. "what's up?", "give me a summary", \
"what do we know so far?", "bring me up to speed"
- **general**: Greetings, acknowledgements, thanks, off-topic, or unclear intent. \
E.g. "hey Sam", "ok thanks", "got it"

Respond with JSON only:
{"skill": "<one of: debug, ideate, investigate, recall, summarize, general>", \
"confidence": <0.0-1.0>, "reasoning": "<one sentence>"}
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

            try:
                skill = Skill(data["skill"].lower())
            except ValueError:
                logger.warning(
                    "LLM returned unknown skill %r — defaulting to GENERAL",
                    data["skill"],
                )
                skill = Skill.GENERAL
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
