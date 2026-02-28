"""Ideate skill — brainstorming solutions and exploring options."""

from __future__ import annotations

from openai import AsyncOpenAI

from war_room_copilot.models import SkillResult, SkillType

SYSTEM_PROMPT = """You are a creative problem-solver in a production incident war room.
The team is brainstorming solutions. Help them think through options.

Your approach:
1. Acknowledge the constraint they're working within
2. Offer 2-3 concrete alternatives they might not have considered
3. For each option, give a quick risk/effort assessment
4. Highlight which option you'd recommend and why

Keep it practical — these are engineers under time pressure, not a design review.
"""


class IdeateSkill:
    def __init__(self) -> None:
        self._client = AsyncOpenAI()

    async def run(self, context: str, user_message: str) -> SkillResult:
        resp = await self._client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion:\n{user_message}"},
            ],
            temperature=0.7,
        )
        content = resp.choices[0].message.content or ""
        return SkillResult(skill=SkillType.IDEATE, content=content, confidence=0.75)
