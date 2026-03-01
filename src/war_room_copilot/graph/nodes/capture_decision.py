"""Decision capture — detects decisions in transcript utterances."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from war_room_copilot.graph.llm import get_graph_llm

logger = logging.getLogger("war-room-copilot.graph.nodes.capture_decision")

DECISION_SYSTEM_PROMPT = SystemMessage(
    content="""\
You are a decision tracker for a production incident war room.
Analyze the latest utterances for decisions being made. Decisions include:
- Actions to take ("let's roll back", "restart the pods", "page the DB team")
- Conclusions reached ("it's the payment service", "root cause is the config change")
- Assignments ("Alice will check the logs", "Bob owns the rollback")

If a decision was made, respond with JSON:
{"found": true, "decision": "Roll back checkout-service to v2.3.1", \
"speaker": "Alice", "type": "action"}

type must be one of: action, conclusion, assignment

If no decision detected:
{"found": false}

Reply with ONLY the JSON object."""
)


async def run_decision_check(
    transcript_lines: list[str],
) -> dict[str, Any] | None:
    """Analyze recent transcript lines for decisions.

    Returns the parsed JSON result dict, or None on failure.
    """
    if len(transcript_lines) < 1:
        return None

    llm = get_graph_llm()
    messages = [
        DECISION_SYSTEM_PROMPT,
        HumanMessage(content="Recent utterances:\n" + "\n".join(transcript_lines)),
    ]

    try:
        response = await llm.ainvoke(messages)
        text = str(response.content).strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(text)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, Exception):
        logger.exception("Decision check failed")
        return None
