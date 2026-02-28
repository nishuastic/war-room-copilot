"""Runbook lookup tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

MOCK_DATA_DIR = Path(__file__).parent.parent.parent.parent / "mock_data"


def search_runbooks(query: str) -> list[dict[str, Any]]:
    """Search runbooks by keyword."""
    try:
        if yaml is None:
            return [{"error": "PyYAML not installed"}]
        data = yaml.safe_load((MOCK_DATA_DIR / "runbooks.yaml").read_text())
        runbooks = data.get("runbooks", [])
        query_lower = query.lower()
        return [
            r
            for r in runbooks
            if query_lower in r.get("title", "").lower()
            or query_lower in r.get("description", "").lower()
            or any(query_lower in tag.lower() for tag in r.get("tags", []))
        ]
    except FileNotFoundError:
        return [{"error": "Mock data not found"}]


RUNBOOK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_runbooks",
            "description": "Search incident runbooks by keyword or tag",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
                "required": ["query"],
            },
        },
    },
]
