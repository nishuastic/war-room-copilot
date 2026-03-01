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
Given the transcript, findings, and decisions so far, produce a \
brief summary.
Focus on: what happened, what has been investigated, what was \
decided, and what is still open.
Keep it under 200 words. Do not use markdown.
Speak in plain language suitable for text-to-speech."""
)

TIMELINE_SYSTEM_PROMPT = SystemMessage(
    content="""\
You are generating a chronological incident timeline for a war room.
Given the transcript with timestamps and speaker labels, produce a \
concise timeline.
Format each entry as: "Time — Speaker — What happened"
Only include significant events: alerts, decisions, findings, \
actions taken.
Skip filler conversation. Keep it under 15 entries.
Do not use markdown. Speak in plain language for text-to-speech."""
)

_TIMELINE_KEYWORDS = {
    "timeline",
    "chronological",
    "what happened when",
    "sequence of events",
    "time line",
}


def _wants_timeline(query: str) -> bool:
    """Check if the user is asking for a timeline specifically."""
    q = query.lower()
    return any(kw in q for kw in _TIMELINE_KEYWORDS)


async def summarize_node(state: IncidentState) -> dict[str, Any]:
    """Produce a summary or timeline of the incident so far."""
    transcript = state.get("transcript", [])
    findings = state.get("findings", [])
    decisions = state.get("decisions", [])
    query = state.get("query", "")

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
            "findings": [summary],
            "messages": [AIMessage(content=summary)],
        }

    # Pick timeline vs summary prompt based on user query
    system_prompt = TIMELINE_SYSTEM_PROMPT if _wants_timeline(query) else SUMMARIZE_SYSTEM_PROMPT

    llm = get_graph_llm()
    messages = [
        system_prompt,
        HumanMessage(content="\n\n".join(context_parts)),
    ]

    try:
        response = await llm.ainvoke(messages)
        summary = str(response.content)
    except Exception:
        logger.exception("Summarization failed")
        summary = "Unable to generate summary at this time."

    return {
        "findings": [summary],
        "messages": [AIMessage(content=summary)],
    }
