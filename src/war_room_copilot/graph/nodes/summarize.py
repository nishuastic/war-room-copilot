"""Summarize node — generates a concise incident summary from accumulated state."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from war_room_copilot.graph.llm import get_graph_llm
from war_room_copilot.graph.state import IncidentState

logger = logging.getLogger("war-room-copilot.graph.nodes.summarize")

SUMMARIZE_SYSTEM_PROMPT = SystemMessage(
    content="""\
You are an incident summarizer for a production war room.
Given the transcript, findings, and decisions so far, produce a brief summary.
Focus on: what happened, what has been investigated, what was decided, and what is still open.
Keep it under 200 words. Do not use markdown.
Speak in plain language suitable for text-to-speech."""
)


async def summarize_node(state: IncidentState) -> dict[str, Any]:
    """Produce a summary of the incident so far."""
    transcript = state.get("transcript", [])
    findings = state.get("findings", [])
    decisions = state.get("decisions", [])

    context_parts: list[str] = []
    if transcript:
        context_parts.append("Transcript (recent):\n" + "\n".join(transcript[-20:]))
    if findings:
        context_parts.append("Findings:\n" + "\n".join(findings[-10:]))
    if decisions:
        context_parts.append("Decisions:\n" + "\n".join(decisions))

    if not context_parts:
        summary = "No incident data to summarize yet."
        return {
            "findings": state.get("findings", []) + [summary],
            "messages": [AIMessage(content=summary)],
        }

    llm = get_graph_llm()
    messages = [
        SUMMARIZE_SYSTEM_PROMPT,
        HumanMessage(content="\n\n".join(context_parts)),
    ]

    try:
        response = await llm.ainvoke(messages)
        summary = str(response.content)
    except Exception:
        logger.exception("Summarization failed")
        summary = "Unable to generate summary at this time."

    return {
        "findings": state.get("findings", []) + [summary],
        "messages": [AIMessage(content=summary)],
    }
