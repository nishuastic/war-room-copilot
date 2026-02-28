"""Recall tool: query past decisions from SQLite and Backboard long-term memory."""

from __future__ import annotations

from livekit.agents import llm

from ..memory.db import IncidentDB
from ..memory.long_term import LongTermMemory

_db: IncidentDB | None = None
_long_term: LongTermMemory | None = None
_session_id: int | None = None


def set_memory_context(db: IncidentDB, long_term: LongTermMemory, session_id: int) -> None:
    global _db, _long_term, _session_id  # noqa: PLW0603
    _db = db
    _long_term = long_term
    _session_id = session_id


@llm.function_tool()  # type: ignore[misc]
async def recall_decision(query: str) -> str:
    """Recall a decision made during this or past incidents. Use when someone asks about
    a past decision, action item, or agreement."""
    results: list[str] = []

    if _db is not None:
        decisions = await _db.search_decisions(query)
        if decisions:
            results.append("From local records:")
            for d in decisions[:5]:
                results.append(f"- [{d.speaker_id}] {d.text} (confidence: {d.confidence:.1f})")

    if _long_term is not None:
        try:
            memory_result = await _long_term.recall(query)
            if memory_result:
                results.append(f"\nFrom long-term memory:\n{memory_result}")
        except Exception:
            pass

    if not results:
        return "No decisions found matching that query."
    return "\n".join(results)
