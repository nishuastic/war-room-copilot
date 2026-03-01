"""Tests for the structured SSE API format matching frontend TypeScript interfaces."""

from __future__ import annotations

from war_room_copilot.api.main import (
    _format_relative,
    _infer_message_type,
    _speaker_name_to_id,
    _to_decision,
    _to_finding,
    _to_timeline_event,
    _to_trace_step,
    _to_transcript_msg,
)
from war_room_copilot.platforms.livekit import (
    _format_relative as lk_format_relative,
)
from war_room_copilot.platforms.livekit import (
    _infer_finding_source,
)


class TestFormatRelative:
    def test_zero_delta(self) -> None:
        assert _format_relative(100.0, 100.0) == "+00:00"

    def test_positive_delta(self) -> None:
        assert _format_relative(165.0, 100.0) == "+01:05"

    def test_negative_delta_clamps_to_zero(self) -> None:
        assert _format_relative(50.0, 100.0) == "+00:00"

    def test_large_delta(self) -> None:
        assert _format_relative(3700.0, 100.0) == "+60:00"


class TestSpeakerNameToId:
    def test_known_speaker(self) -> None:
        speakers = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        assert _speaker_name_to_id("Alice", speakers) == 1

    def test_unknown_speaker_returns_zero(self) -> None:
        assert _speaker_name_to_id("Unknown", []) == 0

    def test_ai_speaker(self) -> None:
        assert _speaker_name_to_id("War Room Copilot", []) == "ai"
        assert _speaker_name_to_id("AI Agent", []) == "ai"


class TestInferMessageType:
    def test_normal_for_human(self) -> None:
        assert _infer_message_type("Some text", 1) == "normal"

    def test_ai_for_agent(self) -> None:
        assert _infer_message_type("Some insight", "ai") == "ai"

    def test_contradiction_for_agent(self) -> None:
        assert _infer_message_type("Contradiction detected: timing", "ai") == "contradiction"

    def test_decision_for_agent(self) -> None:
        assert _infer_message_type("Decision captured: rollback", "ai") == "decision"


class TestToTranscriptMsg:
    def test_basic_structure(self) -> None:
        entry = {"speaker": "Alice", "text": "Hello", "epoch": 110.0}
        speakers = [{"id": 1, "name": "Alice"}]
        result = _to_transcript_msg(entry, 0, 100.0, speakers)
        assert result == {
            "id": "t1",
            "timestamp": "+00:10",
            "speakerId": 1,
            "text": "Hello",
            "type": "normal",
        }


class TestToFinding:
    def test_basic_structure(self) -> None:
        entry = {"text": "Issue #123 found", "source": "github", "epoch": 200.0}
        result = _to_finding(entry, 0, 100.0)
        assert result == {
            "id": "f1",
            "text": "Issue #123 found",
            "source": "github",
            "timestamp": "+01:40",
        }


class TestToDecision:
    def test_basic_structure(self) -> None:
        entry = {"text": "Rollback deploy", "speaker": "Alice", "epoch": 300.0}
        result = _to_decision(entry, 2, 100.0)
        assert result == {
            "id": "d3",
            "number": 3,
            "text": "Rollback deploy",
            "speaker": "Alice",
            "timestamp": "+03:20",
        }


class TestToTraceStep:
    def test_basic_structure(self) -> None:
        entry = {"node": "investigate", "query": "search code", "duration": 1.5, "epoch": 150.0}
        result = _to_trace_step(entry, 0, 100.0)
        assert result == {
            "id": "s1",
            "skill": "investigate",
            "query": "search code",
            "duration": 1.5,
            "status": "completed",
            "timestamp": "+00:50",
        }


class TestToTimelineEvent:
    def test_basic_structure(self) -> None:
        entry = {"type": "finding", "description": "Found issue", "epoch": 200.0}
        result = _to_timeline_event(entry, 0, 100.0)
        assert result == {
            "id": "e1",
            "type": "finding",
            "description": "Found issue",
            "timestamp": "+01:40",
        }


class TestInferFindingSource:
    def test_github_keywords(self) -> None:
        assert _infer_finding_source("Issue #123 found") == "github"
        assert _infer_finding_source("PR merged yesterday") == "github"
        assert _infer_finding_source("Recent commit added query") == "github"

    def test_metrics_keywords(self) -> None:
        assert _infer_finding_source("p99 latency spike") == "metrics"
        assert _infer_finding_source("Error rate at 5%") == "metrics"

    def test_code_default(self) -> None:
        assert _infer_finding_source("Found in application logs") == "code"


class TestLkFormatRelative:
    def test_matches_api_format(self) -> None:
        assert lk_format_relative(165.0, 100.0) == "+01:05"
