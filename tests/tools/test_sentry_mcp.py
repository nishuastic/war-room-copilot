"""Tests for Sentry MCP client pure helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from war_room_copilot.tools.sentry_mcp import (
    _extract_text,
    _parse_json_response,
    format_sentry_events_for_llm,
    format_sentry_issues_for_llm,
)


# ── format_sentry_issues_for_llm ─────────────────────────────────────────────


def test_format_sentry_issues_empty() -> None:
    """Empty issue list returns 'none'."""
    result = format_sentry_issues_for_llm([])
    assert result == "Sentry Issues: none"


def test_format_sentry_issues_with_data() -> None:
    """Sample issues include title, level, and count."""
    issues = [
        {
            "id": "123",
            "title": "TimeoutError: connection timed out",
            "level": "error",
            "count": 42,
            "culprit": "db.pool.get_connection",
            "lastSeen": "2026-03-01T10:00:00Z",
            "permalink": "https://sentry.io/issues/123/",
        },
        {
            "id": "456",
            "title": "Warning: slow query detected",
            "level": "warning",
            "count": 7,
        },
    ]

    result = format_sentry_issues_for_llm(issues)

    assert "Sentry Issues (2):" in result
    assert "[ERROR]" in result
    assert "TimeoutError" in result
    assert "count=42" in result
    assert "db.pool.get_connection" in result
    assert "[WARNING]" in result
    assert "slow query" in result


# ── format_sentry_events_for_llm ─────────────────────────────────────────────


def test_format_sentry_events_empty() -> None:
    """Empty event list returns 'none'."""
    result = format_sentry_events_for_llm([])
    assert result == "Sentry Events: none"


def test_format_sentry_events_with_data() -> None:
    """Events include timestamp and exception info."""
    events = [
        {
            "eventID": "abc12345def67890",
            "timestamp": "2026-03-01T10:05:00Z",
            "message": "Connection timed out",
            "entries": [
                {
                    "type": "exception",
                    "data": {
                        "values": [
                            {
                                "type": "TimeoutError",
                                "value": "connection pool exhausted",
                                "stacktrace": {
                                    "frames": [
                                        {
                                            "filename": "db/pool.py",
                                            "lineNo": 42,
                                            "function": "get_connection",
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                }
            ],
        },
    ]

    result = format_sentry_events_for_llm(events, issue_title="DB Timeout")

    assert "Sentry Events for 'DB Timeout'" in result
    assert "2026-03-01T10:05:00Z" in result
    assert "TimeoutError" in result
    assert "connection pool exhausted" in result
    assert "db/pool.py:42" in result
    assert "get_connection" in result


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


def test_extract_text_blocks_without_text() -> None:
    """Blocks without .text fall back to str()."""
    result = _extract_text(["plain", "strings"])
    assert "plain" in result
    assert "strings" in result


# ── _parse_json_response ─────────────────────────────────────────────────────


def test_parse_json_valid_list() -> None:
    """Valid JSON list is parsed correctly."""
    b = MagicMock()
    b.text = '[{"id": 1}, {"id": 2}]'
    result = _parse_json_response([b])
    assert len(result) == 2
    assert result[0]["id"] == 1


def test_parse_json_valid_dict() -> None:
    """Valid JSON dict is wrapped in a list."""
    b = MagicMock()
    b.text = '{"id": 1, "title": "test"}'
    result = _parse_json_response([b])
    assert len(result) == 1
    assert result[0]["id"] == 1


def test_parse_json_invalid() -> None:
    """Invalid JSON returns empty list."""
    b = MagicMock()
    b.text = "not valid json at all"
    result = _parse_json_response([b])
    assert result == []


def test_parse_json_base_exception() -> None:
    """BaseException input returns empty list."""
    result = _parse_json_response(RuntimeError("boom"))
    assert result == []
