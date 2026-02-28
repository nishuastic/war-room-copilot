"""Shared state that flows through the incident investigation graph."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class IncidentState(TypedDict, total=False):
    """Shared state for the incident investigation graph.

    Every node receives the full state and returns a partial update.
    ``messages`` uses the ``add_messages`` reducer so new messages are
    appended rather than replacing the entire list.
    """

    # Conversation history (LLM messages — appended via reducer)
    messages: Annotated[list[Any], add_messages]

    # Raw transcript lines from STT ("<speaker>: text")
    transcript: list[str]

    # Findings from research agents (appended by nodes)
    findings: list[str]

    # Tracked decisions made during the incident
    decisions: list[str]

    # Speaker map: speaker_id -> display name
    speakers: dict[str, str]

    # Which skill the router selected
    routed_skill: str

    # The user's current query / latest utterance
    query: str
