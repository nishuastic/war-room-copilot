"""Incident investigation graph — the main LangGraph definition.

              ┌──────────┐
              │  router  │
              └────┬─────┘
      ┌────────┬───┴───┬──────────┐
      ▼        ▼       ▼          ▼
investigate  summarize recall   respond
 (GitHub)
      │        │       │          │
      └────────┴───┬───┴──────────┘
                   ▼
                 END
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from war_room_copilot.graph.nodes.github_research import github_research_node
from war_room_copilot.graph.nodes.recall import recall_node
from war_room_copilot.graph.nodes.respond import respond_node
from war_room_copilot.graph.nodes.skill_router import skill_router_node
from war_room_copilot.graph.nodes.summarize import summarize_node
from war_room_copilot.graph.state import IncidentState

logger = logging.getLogger("war-room-copilot.graph.incident_graph")


def _route_after_router(state: IncidentState) -> str:
    """Conditional edge: pick the next node based on the router's classification."""
    skill = state.get("routed_skill", "respond")
    return {
        "investigate": "investigate",
        "summarize": "summarize",
        "recall": "recall",
        "respond": "respond",
    }.get(skill, "respond")


def build_incident_graph() -> Any:
    """Construct and compile the incident investigation graph.

    Returns a compiled graph ready for ``ainvoke()`` / ``astream()``.
    """
    graph = StateGraph(IncidentState)

    # Add nodes
    graph.add_node("router", skill_router_node)
    graph.add_node("investigate", github_research_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("recall", recall_node)
    graph.add_node("respond", respond_node)

    # Entry point
    graph.set_entry_point("router")

    # Router -> skill nodes (conditional)
    graph.add_conditional_edges(
        "router",
        _route_after_router,
        {
            "investigate": "investigate",
            "summarize": "summarize",
            "recall": "recall",
            "respond": "respond",
        },
    )

    # All skill nodes -> END
    graph.add_edge("investigate", END)
    graph.add_edge("summarize", END)
    graph.add_edge("recall", END)
    graph.add_edge("respond", END)

    return graph.compile()


# Module-level compiled graph — import and use directly.
incident_graph = build_incident_graph()
