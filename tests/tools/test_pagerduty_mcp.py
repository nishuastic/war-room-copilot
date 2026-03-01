"""Tests for PagerDuty MCP client pure helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from war_room_copilot.tools.pagerduty_mcp import (
    _extract_text,
    _parse_json_response,
    format_incidents_for_llm,
    format_oncall_for_llm,
    format_services_for_llm,
)

# ── format_incidents_for_llm ─────────────────────────────────────────────────


def test_format_incidents_empty() -> None:
    """Empty incident list returns 'none active'."""
    result = format_incidents_for_llm([])
    assert result == "PagerDuty Incidents: none active"


def test_format_incidents_with_data() -> None:
    """Sample incidents include title, status, and urgency."""
    incidents = [
        {
            "incident_number": 42,
            "title": "Database connection pool exhausted",
            "status": "triggered",
            "urgency": "high",
            "service": {"summary": "checkout-service"},
            "created_at": "2026-03-01T10:00:00Z",
        },
        {
            "incident_number": 43,
            "title": "High latency on API gateway",
            "status": "acknowledged",
            "urgency": "low",
        },
    ]

    result = format_incidents_for_llm(incidents)

    assert "PagerDuty Active Incidents (2):" in result
    assert "#42" in result
    assert "triggered" in result
    assert "high" in result
    assert "Database connection pool" in result
    assert "checkout-service" in result
    assert "#43" in result
    assert "acknowledged" in result
    assert "High latency" in result


# ── format_oncall_for_llm ────────────────────────────────────────────────────


def test_format_oncall_empty() -> None:
    """Empty on-call list returns 'no schedules'."""
    result = format_oncall_for_llm([])
    assert result == "PagerDuty On-Call: no schedules found"


def test_format_oncall_with_data() -> None:
    """Sample on-call data includes user name and schedule."""
    oncalls = [
        {
            "user": {"summary": "Jane Doe"},
            "schedule": {"summary": "Primary On-Call"},
            "escalation_policy": {"summary": "Engineering"},
            "escalation_level": 1,
        },
        {
            "user": {"summary": "John Smith"},
            "schedule": {"summary": "Secondary On-Call"},
            "escalation_policy": {},
            "escalation_level": 2,
        },
    ]

    result = format_oncall_for_llm(oncalls)

    assert "PagerDuty On-Call (2 entries):" in result
    assert "Jane Doe" in result
    assert "Primary On-Call" in result
    assert "Engineering" in result
    assert "L1:" in result
    assert "John Smith" in result
    assert "L2:" in result


# ── format_services_for_llm ──────────────────────────────────────────────────


def test_format_services_empty() -> None:
    """Empty services list returns 'none found'."""
    result = format_services_for_llm([])
    assert result == "PagerDuty Services: none found"


def test_format_services_with_data() -> None:
    """Sample services include name and status."""
    services = [
        {
            "name": "checkout-service",
            "status": "active",
            "description": "Handles payment processing",
        },
        {
            "name": "api-gateway",
            "status": "warning",
        },
    ]

    result = format_services_for_llm(services)

    assert "PagerDuty Services (2):" in result
    assert "checkout-service" in result
    assert "[active]" in result
    assert "Handles payment processing" in result
    assert "api-gateway" in result
    assert "[warning]" in result


# ── _extract_text ─────────────────────────────────────────────────────────────


def test_extract_text_with_blocks() -> None:
    """List of blocks with .text is joined with spaces."""
    b1 = MagicMock()
    b1.text = "hello"
    b2 = MagicMock()
    b2.text = "world"

    result = _extract_text([b1, b2])
    assert result == "hello world"


def test_extract_text_with_plain_string() -> None:
    """Non-list input is converted via str()."""
    result = _extract_text("just a string")
    assert result == "just a string"


# ── _parse_json_response ─────────────────────────────────────────────────────


def test_parse_json_valid_list() -> None:
    """Valid JSON list is parsed correctly."""
    b = MagicMock()
    b.text = '[{"id": 1}, {"id": 2}]'
    result = _parse_json_response([b])
    assert len(result) == 2


def test_parse_json_valid_dict_with_incidents_key() -> None:
    """PagerDuty-style dict with 'incidents' key unwraps the array."""
    b = MagicMock()
    b.text = '{"incidents": [{"id": "P1"}, {"id": "P2"}]}'
    result = _parse_json_response([b])
    assert len(result) == 2
    assert result[0]["id"] == "P1"


def test_parse_json_valid_dict_with_oncalls_key() -> None:
    """PagerDuty-style dict with 'oncalls' key unwraps the array."""
    b = MagicMock()
    b.text = '{"oncalls": [{"user": {"name": "Jane"}}]}'
    result = _parse_json_response([b])
    assert len(result) == 1
    assert result[0]["user"]["name"] == "Jane"


def test_parse_json_invalid() -> None:
    """Invalid JSON returns empty list."""
    b = MagicMock()
    b.text = "not valid json"
    result = _parse_json_response([b])
    assert result == []


def test_parse_json_base_exception() -> None:
    """BaseException input returns empty list."""
    result = _parse_json_response(RuntimeError("connection refused"))
    assert result == []
