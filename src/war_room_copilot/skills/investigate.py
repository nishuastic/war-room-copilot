"""Investigate skill — data lookup via tools (logs, metrics, code search)."""

from __future__ import annotations

from openai import AsyncOpenAI

from war_room_copilot.models import SkillResult, SkillType

SYSTEM_PROMPT = """You are an investigator in a production incident war room.
When the team needs data, you query the right tools and present findings clearly.

Available tools:
- search_github: Search code, commits, PRs in the repository
- query_logs: Search application logs by service, level, timerange
- query_metrics: Get metrics (latency, error rate, throughput) for a service
- get_service_graph: Show service dependency graph

Your approach:
1. Determine what data is needed
2. Call the appropriate tool(s)
3. Present findings concisely with key data points highlighted
4. Note any anomalies or correlations
"""


class InvestigateSkill:
    def __init__(self) -> None:
        self._client = AsyncOpenAI()

    async def run(self, context: str, user_message: str) -> SkillResult:
        resp = await self._client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nInvestigation request:\n{user_message}",
                },
            ],
            temperature=0.2,
        )
        content = resp.choices[0].message.content or ""
        return SkillResult(skill=SkillType.INVESTIGATE, content=content, confidence=0.85)
