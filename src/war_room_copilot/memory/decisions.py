"""Decision tracking — detect, store, and recall decisions from conversations."""

from __future__ import annotations

import logging
import uuid

from openai import AsyncOpenAI

from war_room_copilot.models import Decision, TranscriptWindow

logger = logging.getLogger("war-room-copilot.decisions")

DECISION_DETECTION_PROMPT = (
    """Analyze the following conversation transcript """
    """and extract any decisions that were made.
A decision is when participants agree on an action, approach, or conclusion.

For each decision, provide:
- summary: one-line description of the decision
- speaker: who proposed/confirmed it
- context: surrounding discussion

Transcript:
{transcript}

Return JSON array of decisions. If no decisions, return empty array [].
"""
)


class DecisionTracker:
    def __init__(self) -> None:
        self._decisions: list[Decision] = []
        self._client = AsyncOpenAI()

    async def detect_decisions(self, window: TranscriptWindow) -> list[Decision]:
        """Run LLM to detect decisions in recent transcript."""
        if not window.chunks:
            return []

        try:
            resp = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You extract decisions from conversations. "
                        "Return valid JSON only.",
                    },
                    {
                        "role": "user",
                        "content": DECISION_DETECTION_PROMPT.format(transcript=window.full_text),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            import json

            content = resp.choices[0].message.content or "{}"
            data = json.loads(content)
            decisions_data = data.get("decisions", data) if isinstance(data, dict) else data
            if not isinstance(decisions_data, list):
                return []

            new_decisions = []
            for d in decisions_data:
                decision = Decision(
                    id=str(uuid.uuid4()),
                    summary=d.get("summary", ""),
                    speaker=d.get("speaker", "unknown"),
                    context=d.get("context", ""),
                )
                self._decisions.append(decision)
                new_decisions.append(decision)
            return new_decisions
        except Exception:
            logger.warning("Decision detection failed", exc_info=True)
            return []

    def get_all(self) -> list[Decision]:
        return list(self._decisions)

    def search(self, query: str) -> list[Decision]:
        query_lower = query.lower()
        return [
            d
            for d in self._decisions
            if query_lower in d.summary.lower() or query_lower in d.context.lower()
        ]
