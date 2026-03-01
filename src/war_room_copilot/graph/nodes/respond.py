"""Respond node — handles general conversation that doesn't need specialized skills."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from war_room_copilot.graph.llm import classify_llm_error, get_graph_llm
from war_room_copilot.graph.state import IncidentState
from war_room_copilot.tools.github_mcp import LLMRateLimitError, LLMTimeoutError

logger = logging.getLogger("war-room-copilot.graph.nodes.respond")

RESPOND_SYSTEM_PROMPT = SystemMessage(
    content="""\
You are War Room Copilot, an AI assistant embedded in a production incident call.
Respond helpfully and concisely. You have access to the incident context below.
Do not use markdown. Keep responses short and clear, suitable for text-to-speech."""
)


async def respond_node(state: IncidentState) -> dict[str, Any]:
    """Generate a direct response using conversation history and context."""
    query = state.get("query", "")
    findings = state.get("findings", [])
    decisions = state.get("decisions", [])

    context_parts: list[str] = []
    if findings:
        context_parts.append("Known findings:\n" + "\n".join(findings[-5:]))
    if decisions:
        context_parts.append("Decisions:\n" + "\n".join(decisions))

    system_content = RESPOND_SYSTEM_PROMPT.content
    if context_parts:
        system_content += "\n\nIncident context:\n" + "\n\n".join(context_parts)  # type: ignore[operator]

    llm = get_graph_llm()
    messages = [
        SystemMessage(content=str(system_content)),
        *state.get("messages", [])[-10:],
        HumanMessage(content=query),
    ]

    try:
        response = await llm.ainvoke(messages)
        result = str(response.content)
    except Exception as exc:
        llm_err = classify_llm_error(exc)
        logger.error(
            "Response generation failed (%s): %s",
            type(llm_err).__name__,
            llm_err,
        )
        if isinstance(llm_err, LLMRateLimitError):
            result = "I'm hitting the LLM rate limit. Please wait a moment and try again."
        elif isinstance(llm_err, LLMTimeoutError):
            result = "The LLM request timed out. Please try again."
        else:
            result = f"I'm having trouble responding — {llm_err}"

    return {"messages": [AIMessage(content=result)]}
