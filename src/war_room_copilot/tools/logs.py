"""Mock log queries returning realistic data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MOCK_DATA_DIR = Path(__file__).parent.parent.parent.parent / "mock_data"


def query_logs(
    service: str,
    level: str = "error",
    keyword: str = "",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Query mock application logs."""
    try:
        data = json.loads((MOCK_DATA_DIR / "application_logs.json").read_text())
        logs = data.get("logs", [])
        filtered = logs
        if service:
            filtered = [e for e in filtered if e.get("service") == service]
        if level:
            filtered = [e for e in filtered if e.get("level", "").lower() == level.lower()]
        if keyword:
            filtered = [e for e in filtered if keyword.lower() in e.get("message", "").lower()]
        return filtered[:limit]
    except FileNotFoundError:
        return [{"error": "Mock data not found. Create mock_data/application_logs.json"}]


LOGS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_logs",
            "description": "Search application logs by service, level, and keyword",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "level": {"type": "string", "enum": ["error", "warn", "info", "debug"]},
                    "keyword": {"type": "string", "description": "Text search in log messages"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["service"],
            },
        },
    },
]
