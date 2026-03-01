"""Shared state that flows through the incident investigation graph."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class IncidentState(TypedDict, total=False):
    """Shared state for the incident investigation graph.

    Every node receives the full state and returns a partial update.
    ``messages`` uses the ``add_messages`` reducer so new messages are
    appended rather than replacing the entire list.  ``transcript``,
    ``findings``, and ``decisions`` use ``operator.add`` so nodes can
    return just the *new* items and they are appended automatically.
    """

    # Conversation history (LLM messages — appended via reducer)
    messages: Annotated[list[Any], add_messages]

    # Raw transcript lines from STT ("<speaker>: text")
    transcript: Annotated[list[str], operator.add]

    # Findings from research agents (appended by nodes)
    findings: Annotated[list[str], operator.add]

    # Tracked decisions made during the incident
    decisions: Annotated[list[str], operator.add]

    # Speaker map: speaker_id -> display name
    speakers: dict[str, str]

    # Which skill the router selected
    routed_skill: str

    # The user's current query / latest utterance
    query: str

    # Backboard thread ID for cross-session memory (injected by platform)
    backboard_thread_id: str
