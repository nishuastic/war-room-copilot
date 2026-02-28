"""Skill router — classifies intent and dispatches to specialized skills."""

from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from war_room_copilot.models import SkillResult, SkillType

logger = logging.getLogger("war-room-copilot.router")

ROUTER_PROMPT = """You are a skill router for an incident war room AI copilot.
Given the user's message, classify which skill should handle it.

Skills:
- debug: User is troubleshooting a specific error, stack trace, or failure
- ideate: User is brainstorming solutions, asking "what if", exploring options
- investigate: User wants data lookup — logs, metrics, code search, recent changes
- recall: User asks about past decisions, previous incidents, or "what did we decide"
- summarize: User wants a summary of the conversation, incident, or timeline

Return JSON: {"skill": "<skill_name>", "confidence": <0.0-1.0>}
"""

SYSTEM_PROMPT = (
    """You are War Room Copilot, an expert SRE AI assistant """
    """participating in a production incident war room.

Your role:
- Listen to the conversation and provide targeted, actionable insights
- Surface relevant context (recent deploys, related incidents, metrics)
- Catch contradictions and circular reasoning
- Track decisions and action items
- Query tools (GitHub, metrics, logs) when needed

Communication style:
- Be concise — people are stressed during incidents
- Lead with the most important information
- Cite sources (commit SHAs, metric values, timestamps)
- If uncertain, say so — never fabricate data
- Use technical language appropriate for senior engineers

You have access to tools for querying GitHub, metrics, logs, and service graphs.
When someone asks about code changes, recent deploys, or service behavior,
use the appropriate tool.
"""
)


class SkillRouter:
    def __init__(self) -> None:
        self._client = AsyncOpenAI()

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    async def classify(self, message: str) -> tuple[SkillType, float]:
        """Classify user intent into a skill type."""
        try:
            resp = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": ROUTER_PROMPT},
                    {"role": "user", "content": message},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            content = resp.choices[0].message.content or "{}"
            data = json.loads(content)
            skill_name = data.get("skill", "debug")
            confidence = float(data.get("confidence", 0.5))
            return SkillType(skill_name), confidence
        except Exception:
            logger.warning("Skill classification failed, defaulting to debug", exc_info=True)
            return SkillType.DEBUG, 0.5

    def should_speak(self, result: SkillResult) -> bool:
        """Confidence-gated output decision."""
        from war_room_copilot.config import settings

        return result.confidence >= settings.interjection_confidence_speak

    def should_show_dashboard(self, result: SkillResult) -> bool:
        from war_room_copilot.config import settings

        return result.confidence >= settings.interjection_confidence_dashboard
