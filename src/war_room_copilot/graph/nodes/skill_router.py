"""Skill router node — classifies intent and decides which skill to invoke."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from war_room_copilot.graph.llm import get_graph_llm
from war_room_copilot.graph.state import IncidentState

logger = logging.getLogger("war-room-copilot.graph.nodes.skill_router")

ROUTER_SYSTEM_PROMPT = SystemMessage(
    content="""\
You are a skill router for an incident response AI copilot.
Given the user's latest utterance and conversation context, classify the intent
into exactly ONE of these skills:

- investigate: User wants to look up code, commits, PRs, issues, or debug info
- summarize: User wants a summary of the incident so far, or a recap
- recall: User is asking about a previous decision or earlier discussion point
- contradict: User asks to check for contradictions or inconsistencies in what was said
- postmortem: User asks for a post-mortem, incident report, or wrap-up document
- respond: General conversation, greetings, or questions you can answer directly

Reply with ONLY the skill name, nothing else. For example: investigate"""
)

VALID_SKILLS = {
    "investigate",
    "summarize",
    "recall",
    "respond",
    "contradict",
    "postmortem",
}


async def skill_router_node(state: IncidentState) -> dict[str, Any]:
    """Classify the user's intent and set ``routed_skill`` in state."""
    query = state.get("query", "")
    if not query:
        return {"routed_skill": "respond"}

    llm = get_graph_llm()
    messages = [ROUTER_SYSTEM_PROMPT, *state.get("messages", [])[-5:]]

    try:
        response = await llm.ainvoke(messages)
        skill = str(response.content).strip().lower()
        if skill not in VALID_SKILLS:
            logger.warning("Router returned unknown skill %r, defaulting to respond", skill)
            skill = "respond"
    except Exception:
        logger.exception("Skill routing failed, defaulting to respond")
        skill = "respond"

    logger.info("Routed query to skill: %s", skill)
    return {
        "routed_skill": skill,
        "messages": [AIMessage(content=f"[Router] Skill: {skill}")],
    }
