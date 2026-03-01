"""Contradiction detection node — finds inconsistencies in the transcript."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from war_room_copilot.graph.llm import get_graph_llm
from war_room_copilot.graph.state import IncidentState

logger = logging.getLogger("war-room-copilot.graph.nodes.contradict")

CONTRADICT_SYSTEM_PROMPT = SystemMessage(
    content="""\
You are a contradiction detector for a production incident war room.
Analyze the transcript below for:
1. Factual contradictions (someone says X, later someone says not-X)
2. Timeline inconsistencies (conflicting times, sequences)
3. Circular reasoning (team revisiting the same hypothesis repeatedly)

If you find a contradiction, respond with a JSON object:
{"found": true, "confidence": 0.0-1.0, "summary": "Brief description \
suitable for text-to-speech", "speaker1": "name", "claim1": "what they said", \
"speaker2": "name", "claim2": "the contradicting claim"}

If no contradictions found:
{"found": false}

Only flag clear contradictions with confidence > 0.6. \
Do not flag ambiguity or opinions. Reply with ONLY the JSON object."""
)


async def contradict_node(state: IncidentState) -> dict[str, Any]:
    """Analyze transcript for contradictions (graph skill path)."""
    transcript = state.get("transcript", [])
    result = await run_contradiction_check(transcript[-30:])

    if result and result.get("found") and result.get("confidence", 0) > 0.7:
        summary = result.get("summary", "A contradiction was detected.")
        return {
            "findings": state.get("findings", []) + [f"Contradiction detected: {summary}"],
            "messages": [AIMessage(content=summary)],
        }

    msg = "No clear contradictions found in the recent transcript."
    return {
        "messages": [AIMessage(content=msg)],
    }


async def run_contradiction_check(
    transcript_lines: list[str],
) -> dict[str, Any] | None:
    """Run contradiction analysis on a window of transcript lines.

    Used both by the graph node and the background monitoring task.
    Returns the parsed JSON result dict, or None on failure.
    """
    if len(transcript_lines) < 3:
        return None

    llm = get_graph_llm()
    messages = [
        CONTRADICT_SYSTEM_PROMPT,
        HumanMessage(content="Transcript:\n" + "\n".join(transcript_lines)),
    ]

    try:
        response = await llm.ainvoke(messages)
        text = str(response.content).strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(text)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, Exception):
        logger.exception("Contradiction check failed")
        return None
