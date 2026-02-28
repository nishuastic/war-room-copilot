"""Contradict skill — passive monitoring for contradictions and circular reasoning."""

from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from war_room_copilot.models import InterjectionDecision, TranscriptWindow

logger = logging.getLogger("war-room-copilot.contradict")

SYSTEM_PROMPT = (
    """You are a contradiction detector monitoring a """
    """production incident war room conversation.

Your job is to analyze the conversation transcript and detect:
1. **Factual contradictions**: Someone says X, but earlier they or someone else said the opposite
   (e.g., "deploy was at 2pm" vs "deploy was at 3pm")
2. **Circular reasoning**: The team has returned to the same hypothesis
   3+ times without new evidence
3. **Data conflicts**: Someone claims something that contradicts known tool data
   (e.g., "DB is fine" when metrics show high latency)
4. **Stale assumptions**: Early assumptions that later evidence has invalidated

For each issue found, provide:
- should_interject: true if this is worth raising
- confidence: 0.0-1.0 how certain you are
- content: what to say (concise, diplomatic, cite specifics)
- reasoning: why this matters
- contradictions: list of specific contradictions found

Return JSON with these fields. If nothing found, return
{"should_interject": false, "confidence": 0.0, "content": "",
"reasoning": "", "contradictions": []}.
"""
)


class ContradictSkill:
    def __init__(self) -> None:
        self._client = AsyncOpenAI()

    async def analyze(self, window: TranscriptWindow) -> InterjectionDecision:
        if not window.chunks:
            return InterjectionDecision()

        try:
            resp = await self._client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Transcript (last {len(window.chunks)} chunks):"
                            f"\n\n{window.full_text}"
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = resp.choices[0].message.content or "{}"
            data = json.loads(content)
            return InterjectionDecision(
                should_interject=data.get("should_interject", False),
                confidence=float(data.get("confidence", 0.0)),
                content=data.get("content", ""),
                reasoning=data.get("reasoning", ""),
                contradictions=data.get("contradictions", []),
            )
        except Exception:
            logger.warning("Contradiction analysis failed", exc_info=True)
            return InterjectionDecision()
