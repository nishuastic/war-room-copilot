"""Tests for incident graph routing logic."""

from __future__ import annotations

import pytest

from war_room_copilot.graph.incident_graph import _route_after_router

# ── _route_after_router ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "skill",
    ["investigate", "summarize", "recall", "respond", "contradict", "postmortem"],
)
def test_route_valid_skills(skill: str) -> None:
    """Each valid skill name routes to itself."""
    assert _route_after_router({"routed_skill": skill}) == skill


def test_route_unknown_defaults_respond() -> None:
    """Unknown skill falls back to 'respond'."""
    assert _route_after_router({"routed_skill": "banana"}) == "respond"


def test_route_missing_key_defaults_respond() -> None:
    """Missing routed_skill key defaults to 'respond'."""
    assert _route_after_router({}) == "respond"
