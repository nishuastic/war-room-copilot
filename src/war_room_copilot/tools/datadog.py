"""Datadog tool wrappers — query metrics, traces, logs via API or MCP."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("war-room-copilot.tools.datadog")

MOCK_DATA_DIR = Path(__file__).parent.parent.parent.parent / "mock_data"


class DatadogTool:
    """Queries Datadog. Falls back to mock data when API is not configured."""

    def __init__(self, api_key: str = "", app_key: str = "") -> None:
        self._api_key = api_key
        self._app_key = app_key

    def query_metrics(
        self, service: str, metric: str = "latency", period: str = "1h"
    ) -> dict[str, Any]:
        """Query metrics for a service."""
        if self._api_key:
            # TODO: Real Datadog API call
            pass

        # Mock fallback
        try:
            data = json.loads((MOCK_DATA_DIR / "datadog_spans.json").read_text())
            service_data = [s for s in data.get("spans", []) if s.get("service") == service]
            return {
                "service": service,
                "metric": metric,
                "period": period,
                "data": service_data[:20],
            }
        except Exception:
            logger.warning("Mock metrics load failed", exc_info=True)
            return {"service": service, "metric": metric, "data": [], "error": "no data available"}

    def query_logs(
        self, service: str, level: str = "error", limit: int = 20
    ) -> list[dict[str, Any]]:
        """Query logs for a service."""
        try:
            data = json.loads((MOCK_DATA_DIR / "application_logs.json").read_text())
            logs = data.get("logs", [])
            filtered = [
                entry
                for entry in logs
                if entry.get("service") == service
                and entry.get("level", "").lower() == level.lower()
            ]
            return filtered[:limit]
        except Exception:
            logger.warning("Mock logs load failed", exc_info=True)
            return []


DATADOG_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_metrics",
            "description": "Query Datadog metrics (latency, error_rate, throughput) for a service",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name"},
                    "metric": {
                        "type": "string",
                        "enum": ["latency", "error_rate", "throughput"],
                        "default": "latency",
                    },
                    "period": {"type": "string", "default": "1h"},
                },
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_logs",
            "description": "Query application logs by service and level",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "level": {
                        "type": "string",
                        "enum": ["error", "warn", "info", "debug"],
                        "default": "error",
                    },
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["service"],
            },
        },
    },
]
