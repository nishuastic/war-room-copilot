"""Recall node — searches incident memory for past decisions and discussion points."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from war_room_copilot.graph.llm import classify_llm_error, get_graph_llm
from war_room_copilot.graph.state import IncidentState
from war_room_copilot.tools.github_mcp import LLMRateLimitError, LLMTimeoutError

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

    # Cross-session memory via Backboard (P1-F)
    try:
        from war_room_copilot.tools.backboard import recall_memory

        thread_id = state.get("backboard_thread_id")
        if thread_id:
            bb_result = await recall_memory(str(thread_id), query)
            if bb_result:
                context_parts.append(f"Cross-session memory:\n{bb_result}")
    except Exception as exc:
        logger.warning("Backboard recall unavailable (%s): %s", type(exc).__name__, exc)

    if decisions:
        context_parts.append("Decisions made:\n" + "\n".join(decisions))
    if findings:
        context_parts.append("Research findings:\n" + "\n".join(findings[-10:]))
    if transcript:
        context_parts.append("Transcript (recent):\n" + "\n".join(transcript[-30:]))

    if not context_parts:
        result = "No incident history to search through yet."
        return {
            "findings": [result],
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
    except Exception as exc:
        llm_err = classify_llm_error(exc)
        logger.error("Recall failed (%s): %s", type(llm_err).__name__, llm_err)
        if isinstance(llm_err, LLMRateLimitError):
            result = "Unable to search memory — LLM rate limit reached. Try again shortly."
        elif isinstance(llm_err, LLMTimeoutError):
            result = "Unable to search memory — LLM request timed out."
        else:
            result = f"Unable to search memory — {type(llm_err).__name__}: {llm_err}"

    return {
        "findings": [result],
        "messages": [AIMessage(content=result)],
    }
