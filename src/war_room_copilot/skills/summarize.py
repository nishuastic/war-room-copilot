"""Summarize skill — generate conversation, incident, or timeline summaries."""

from __future__ import annotations

from openai import AsyncOpenAI

from war_room_copilot.models import SkillResult, SkillType

SYSTEM_PROMPT = """You are a summarizer in a production incident war room.
Create clear, structured summaries of the ongoing incident.

Format:
- **Status**: Current state of the incident
- **Timeline**: Key events in chronological order
- **Root Cause**: Current understanding (or "Under investigation")
- **Decisions Made**: Actions agreed upon
- **Next Steps**: What's happening now / what needs to happen

Be factual — only include what was actually discussed, not speculation.
"""


class SummarizeSkill:
    def __init__(self) -> None:
        self._client = AsyncOpenAI()

    async def run(self, context: str, user_message: str) -> SkillResult:
        resp = await self._client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Full conversation:\n{context}\n\n"
                        f"Summarize request:\n{user_message}"
                    ),
                },
            ],
            temperature=0.2,
        )
        content = resp.choices[0].message.content or ""
        return SkillResult(skill=SkillType.SUMMARIZE, content=content, confidence=0.9)
