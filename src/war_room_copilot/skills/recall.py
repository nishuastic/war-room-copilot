"""Recall skill — retrieve past decisions, incidents, and context from memory."""

from __future__ import annotations

from war_room_copilot.memory.decisions import DecisionTracker
from war_room_copilot.memory.long_term import LongTermMemory
from war_room_copilot.models import SkillResult, SkillType


class RecallSkill:
    def __init__(self, decisions: DecisionTracker, long_term: LongTermMemory) -> None:
        self._decisions = decisions
        self._long_term = long_term

    async def run(self, context: str, user_message: str) -> SkillResult:
        # Search decisions
        local_decisions = self._decisions.search(user_message)

        # Search long-term memory
        memories = await self._long_term.recall(user_message)

        parts: list[str] = []
        if local_decisions:
            parts.append("**Decisions from this session:**")
            for d in local_decisions:
                parts.append(f"- {d.summary} (by {d.speaker}, {d.timestamp.strftime('%H:%M')})")

        if memories:
            parts.append("\n**From past sessions:**")
            for m in memories:
                parts.append(f"- {m.value}")

        if not parts:
            content = "I don't have any stored information matching that query."
            confidence = 0.3
        else:
            content = "\n".join(parts)
            confidence = 0.9

        return SkillResult(skill=SkillType.RECALL, content=content, confidence=confidence)
