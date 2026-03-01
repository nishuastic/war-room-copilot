"""Tests for the demo seed module."""

from __future__ import annotations

from war_room_copilot.api.demo_seed import seed_demo_state


def test_seed_populates_all_fields() -> None:
    """Seed fills transcript, findings, decisions, traces, timeline, speakers."""
    state: dict = {
        "transcript": [],
        "transcript_structured": [],
        "findings": [],
        "findings_structured": [],
        "decisions": [],
        "decisions_structured": [],
        "speakers": {},
        "speakers_list": [],
        "messages": [],
        "graph_traces": [],
        "timeline": [],
        "orb_state": "idle",
        "session_start_epoch": 0,
    }
    seed_demo_state(state)

    assert len(state["transcript_structured"]) == 10
    assert len(state["transcript"]) == 10
    assert len(state["findings_structured"]) == 4
    assert len(state["findings"]) == 4
    assert len(state["decisions_structured"]) == 3
    assert len(state["decisions"]) == 3
    assert len(state["graph_traces"]) == 7
    assert len(state["timeline"]) == 9
    assert len(state["speakers_list"]) == 4
    assert state["orb_state"] == "listening"
    assert state["session_start_epoch"] > 0


def test_seed_speaker_names() -> None:
    """All four speakers are registered."""
    state: dict = {
        "transcript": [], "transcript_structured": [],
        "findings": [], "findings_structured": [],
        "decisions": [], "decisions_structured": [],
        "speakers": {}, "speakers_list": [],
        "messages": [], "graph_traces": [], "timeline": [],
        "orb_state": "idle", "session_start_epoch": 0,
    }
    seed_demo_state(state)

    names = {s["name"] for s in state["speakers_list"]}
    assert names == {"Sarah Chen", "Marcus Johnson", "Priya Patel", "Alex Kim"}


def test_seed_graph_skills_covered() -> None:
    """All key agent skills appear in graph traces."""
    state: dict = {
        "transcript": [], "transcript_structured": [],
        "findings": [], "findings_structured": [],
        "decisions": [], "decisions_structured": [],
        "speakers": {}, "speakers_list": [],
        "messages": [], "graph_traces": [], "timeline": [],
        "orb_state": "idle", "session_start_epoch": 0,
    }
    seed_demo_state(state)

    skills = {t["node"] for t in state["graph_traces"]}
    assert "investigate" in skills
    assert "contradict" in skills
    assert "recall" in skills
    assert "skill_router" in skills
    assert "github" in skills
