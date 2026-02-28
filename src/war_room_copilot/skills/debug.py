"""Debug skill — troubleshooting errors, stack traces, failures."""

from __future__ import annotations

from openai import AsyncOpenAI

from war_room_copilot.models import SkillResult, SkillType

SYSTEM_PROMPT = """You are an expert debugger in a production incident war room.
Given the conversation context, help troubleshoot the issue.

Your approach:
1. Identify the specific error or failure being discussed
2. Suggest likely root causes based on symptoms
3. Recommend specific diagnostic steps (which logs, metrics, code to check)
4. If tools are available, suggest which ones to query

Be precise and actionable. No generic advice — give specific commands,
queries, or code paths to investigate.
"""


class DebugSkill:
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
                        f"Conversation context:\n{context}\n\n"
                        f"Current question:\n{user_message}"
                    ),
                },
            ],
            temperature=0.3,
        )
        content = resp.choices[0].message.content or ""
        return SkillResult(skill=SkillType.DEBUG, content=content, confidence=0.8)
