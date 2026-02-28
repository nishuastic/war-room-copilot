"""Service dependency graph tool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MOCK_DATA_DIR = Path(__file__).parent.parent.parent.parent / "mock_data"


def get_service_graph() -> dict[str, Any]:
    """Return the service dependency graph."""
    try:
        return json.loads((MOCK_DATA_DIR / "service_graph.json").read_text())
    except FileNotFoundError:
        return {"error": "Mock data not found", "services": [], "edges": []}


def get_service_dependencies(service: str) -> dict[str, Any]:
    """Get upstream and downstream dependencies for a service."""
    graph = get_service_graph()
    edges = graph.get("edges", [])
    upstream = [e["from"] for e in edges if e.get("to") == service]
    downstream = [e["to"] for e in edges if e.get("from") == service]
    return {"service": service, "upstream": upstream, "downstream": downstream}


SERVICE_GRAPH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_service_graph",
            "description": "Get the full service dependency graph",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_service_dependencies",
            "description": "Get upstream and downstream dependencies for a specific service",
            "parameters": {
                "type": "object",
                "properties": {"service": {"type": "string", "description": "Service name"}},
                "required": ["service"],
            },
        },
    },
]
