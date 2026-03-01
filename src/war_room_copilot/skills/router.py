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
You are a skill classifier for a production incident war room AI assistant named Sam.

Given the recent conversation context and the user's message, do two things:

1. Determine whether the user is **directly addressing Sam** (the assistant). \
Set "addressed_to_assistant" to true when the user is speaking TO Sam in any way — \
asking Sam to do something, requesting information, greeting Sam, saying Sam's name \
to get attention, or any message where Sam is the intended listener. \
Examples of addressed=true: "Sam, how are you?", "hey Sam", "Sam what happened?", \
"my boy Sam, how are you?", "Sam.", "yo Sam can you check the logs?" \
Set it to false ONLY when "Sam" is mentioned as a third person in conversation \
with other humans — talking ABOUT Sam, not TO Sam. \
Examples of addressed=false: "Sam broke the deploy", "tell Sam about it later", \
"I think Sam's code caused this", "has anyone told Sam?"

2. Classify the intent into EXACTLY one of these six skills. \
You MUST pick from this list — no other values are allowed:

- **debug**: Root cause analysis, "why did this break", trace errors, \
find the cause. E.g. "why is the API returning 500s?", "what caused the spike?"
- **ideate**: Brainstorming solutions, "what should we do", weighing options, \
trade-offs, mitigation strategies. E.g. "should we rollback or hotfix?"
- **investigate**: Proactively look something up OR take an action using tools — \
monitoring, logs, code, commits, PRs, files, service health, runbooks, \
OR write actions like creating GitHub issues, reverting commits, creating PRs. \
E.g. "check the last deploy", "what changed in auth?", "look at the logs", \
"check Datadog APM", "what's the runbook for X", "create a GitHub issue", \
"revert commit", "what are the dependencies for backboard-gateway?"
- **recall**: Asking about past decisions, previous incidents, history. \
E.g. "what did we decide last time?", "have we seen this before?"
- **summarize**: Status updates, recaps, catch-ups, "what's going on", \
"where are we", gathering context. E.g. "what's up?", "give me a summary", \
"what do we know so far?", "bring me up to speed"
- **general**: Greetings, acknowledgements, thanks, off-topic, or unclear intent. \
E.g. "hey Sam", "ok thanks", "got it"

Respond with JSON only:
{"addressed_to_assistant": <true or false>, \
"skill": "<one of: debug, ideate, investigate, recall, summarize, general>", \
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
            addressed = data.get("addressed_to_assistant", True)

            # If not directly addressed to Sam, drop confidence to 0 so agent stays silent
            if not addressed:
                logger.info(
                    "Not addressed to assistant — suppressing response (was %.2f %s)",
                    confidence,
                    skill.value,
                )
                confidence = 0.0
                reasoning = f"Not addressed to assistant. Original: {reasoning}"

            result = SkillResult(skill=skill, confidence=confidence, reasoning=reasoning)
            logger.info(
                "Skill route: %s (%.2f) addressed=%s — %s",
                result.skill.value,
                result.confidence,
                addressed,
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
