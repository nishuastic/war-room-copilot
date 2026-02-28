"""Recall node — searches incident memory for past decisions and discussion points."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from war_room_copilot.graph.llm import get_graph_llm
from war_room_copilot.graph.state import IncidentState

logger = logging.getLogger("war-room-copilot.graph.nodes.recall")

RECALL_SYSTEM_PROMPT = SystemMessage(
    content="""\
You are a memory recall agent for an incident war room.
The user is asking about something that was discussed or decided earlier.
Search through the transcript, decisions, and findings to find the relevant info.
Quote the relevant parts and provide context. Be concise and accurate.
If you cannot find what they are asking about, say so honestly.
Do not use markdown. Keep it suitable for text-to-speech."""
)


async def recall_node(state: IncidentState) -> dict[str, Any]:
    """Search accumulated state for information the user is asking about."""
    query = state.get("query", "")
    transcript = state.get("transcript", [])
    findings = state.get("findings", [])
    decisions = state.get("decisions", [])

    context_parts: list[str] = []
    if decisions:
        context_parts.append("Decisions made:\n" + "\n".join(decisions))
    if findings:
        context_parts.append("Research findings:\n" + "\n".join(findings[-10:]))
    if transcript:
        context_parts.append("Transcript (recent):\n" + "\n".join(transcript[-30:]))

    if not context_parts:
        result = "No incident history to search through yet."
        return {
            "findings": state.get("findings", []) + [result],
            "messages": [AIMessage(content=result)],
        }

    llm = get_graph_llm()
    messages = [
        RECALL_SYSTEM_PROMPT,
        HumanMessage(
            content=f"User is asking: {query}\n\nAvailable context:\n" + "\n\n".join(context_parts)
        ),
    ]

    try:
        response = await llm.ainvoke(messages)
        result = str(response.content)
    except Exception:
        logger.exception("Recall failed")
        result = "Unable to search memory at this time."

    return {
        "findings": state.get("findings", []) + [result],
        "messages": [AIMessage(content=result)],
    }
