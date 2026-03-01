"""Datadog monitoring tools — returns simulated incident data for demos."""

from __future__ import annotations

import logging

from livekit.agents import function_tool

logger = logging.getLogger(__name__)


def _fuzzy_match(name: str, keys: dict) -> str | None:
    """Return the best matching key from *keys* for *name* (case-insensitive, partial)."""
    lower = name.lower()
    # exact (case-insensitive)
    for k in keys:
        if k.lower() == lower:
            return k
    # partial — name contained in key or vice-versa
    for k in keys:
        if lower in k.lower() or k.lower() in lower:
            return k
    return None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@function_tool()
async def query_datadog_metrics(metric: str, from_time: str = "1h", to_time: str = "now") -> str:
    """Query Datadog metrics API for a given metric over a time range.

    Args:
        metric: Metric name, e.g. 'backboard.latency_p99' or 'system.cpu.user'
        from_time: Start time — relative like '1h', '30m', or ISO8601 timestamp
        to_time: End time — 'now' or ISO8601 timestamp
    """
    return (
        f"Metric: {metric}\n"
        f"Time range: last {from_time}\n"
        "Values: [p50=120ms, p95=890ms, p99=12100ms, max=14823ms]\n"
        "Trend: Sharply increasing from 08:00 UTC. "
        "Possible root cause: upstream dependency degradation."
    )


@function_tool()
async def query_datadog_logs(query: str, service: str | None = None, minutes_ago: int = 30) -> str:
    """Query Datadog Log Explorer for matching log entries.

    Args:
        query: Log search query, e.g. 'error timeout' or 'status:error'
        service: Optional service name filter, e.g. 'backboard-gateway'
        minutes_ago: How far back to search (default: last 30 minutes)
    """
    service_filter = f" for service '{service}'" if service else ""
    return (
        f"Datadog log search{service_filter}: '{query}' (last {minutes_ago} min)\n\n"
        "Results:\n"
        "08:02:10Z [ERROR] backboard-gateway — Memory query exceeded SLA: 12100ms\n"
        "08:02:11Z [ERROR] backboard-gateway — Postgres connection pool exhausted:"
        " max_connections=20, waiting=47\n"
        "08:08:00Z [CRITICAL] backboard-gateway — All 20 Postgres connections in use"
        " for >30s. Wait queue depth: 63.\n"
        "\nTotal: 3 matching log entries"
    )


@function_tool()
async def query_datadog_apm(service: str, minutes_ago: int = 30) -> str:
    """Query Datadog APM for trace error rate and latency for a service.

    Args:
        service: Service name in APM, e.g. 'backboard-gateway' or 'livekit-agent'
        minutes_ago: Time window to analyze (default: last 30 minutes)
    """
    mock_data = {
        "backboard-gateway": {
            "p99_ms": 12100,
            "error_rate_pct": 34.0,
            "throughput_rps": 2.3,
            "top_errors": [
                "TimeoutError: Upstream response exceeded 12s",
                "ConnectionError: Postgres pool exhausted",
            ],
        },
        "livekit-agent": {
            "p99_ms": 14823,
            "error_rate_pct": 2.0,
            "throughput_rps": 0.8,
            "top_errors": ["ToolError: Backboard gateway returned 504"],
        },
        "elevenlabs-tts": {
            "p99_ms": 890,
            "error_rate_pct": 41.0,
            "throughput_rps": 1.1,
            "top_errors": ["RateLimitError: 429 Too Many Requests — daily quota exhausted"],
        },
        "speechmatics-proxy": {
            "p99_ms": 2800,
            "error_rate_pct": 1.0,
            "throughput_rps": 3.2,
            "top_errors": [],
        },
        "fastapi-dashboard": {
            "p99_ms": 45,
            "error_rate_pct": 0.0,
            "throughput_rps": 5.4,
            "top_errors": [],
        },
    }
    _default: dict = {
        "p99_ms": "N/A",
        "error_rate_pct": 0.0,
        "throughput_rps": 0,
        "top_errors": [],
    }
    matched_key = _fuzzy_match(service, mock_data)
    data = mock_data[matched_key] if matched_key else _default
    errors_str = "\n  - ".join(data["top_errors"]) if data["top_errors"] else "None"
    if data["top_errors"]:
        errors_str = "\n  - " + errors_str
    return (
        f"APM data for service '{service}' (last {minutes_ago} min):\n"
        f"  p99 Latency: {data['p99_ms']}ms\n"
        f"  Error Rate: {data['error_rate_pct']}%\n"
        f"  Throughput: {data['throughput_rps']} req/s\n"
        f"  Top Errors:{errors_str or ' None'}"
    )


@function_tool()
async def get_datadog_monitors() -> str:
    """List all triggered (alerting or warning) Datadog monitors.

    Returns currently firing monitors with their names, status, and affected services.
    """
    return (
        "Active Datadog monitors (triggered):\n\n"
        "1. [ALERT] 'backboard-gateway p99 latency > 5s' — State: ALERT\n"
        "   Triggered: 2026-03-01 08:02 UTC | Service: backboard-gateway\n"
        "   Message: Latency at 12100ms, threshold 5000ms. Check Postgres connections.\n\n"
        "2. [ALERT] 'ElevenLabs TTS error rate > 20%' — State: ALERT\n"
        "   Triggered: 2026-03-01 08:03 UTC | Service: elevenlabs-tts\n"
        "   Message: Error rate at 41%. Daily quota exhausted (98.4% used).\n\n"
        "3. [WARN] 'Postgres RDS connections > 80%' — State: WARN\n"
        "   Triggered: 2026-03-01 08:01 UTC | Service: postgres-rds\n"
        "   Message: Connection count 100/100. PgBouncer recommended.\n\n"
        "4. [WARN] 'speechmatics-proxy pod restarts > 2 in 1h' — State: WARN\n"
        "   Triggered: 2026-03-01 07:56 UTC | Service: speechmatics-proxy\n"
        "   Message: 4 OOMKill restarts. Running on 1/2 replicas.\n\n"
        "Total: 4 active monitors (2 ALERT, 2 WARN)"
    )
