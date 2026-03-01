"""Datadog monitoring tools — queries metrics, logs, APM traces, and monitors."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Datadog client helpers
# ---------------------------------------------------------------------------

_dd_metrics_api = None
_dd_logs_api = None
_dd_apm_api = None
_dd_monitors_api = None


def _get_dd_configuration():
    """Return a configured Datadog API configuration object."""
    from datadog_api_client import Configuration

    site = os.environ.get("DD_SITE", "datadoghq.com")
    config = Configuration()
    config.api_key["apiKeyAuth"] = os.environ.get("DATADOG_API_KEY") or os.environ.get(
        "DD_API_KEY", ""
    )
    config.api_key["appKeyAuth"] = os.environ.get("DATADOG_APP_KEY") or os.environ.get(
        "DD_APP_KEY", ""
    )
    # server_variables["site"] is used by the SDK to build the base URL.
    # Must match a valid Datadog site hostname (e.g. datadoghq.eu, datadoghq.com).
    config.server_variables["site"] = site
    # For EU and other non-US1 sites, also set the host directly to be safe.
    config.host = f"https://api.{site}"
    return config


def _truncate(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated at {limit} chars]"


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
    api_key = os.environ.get("DATADOG_API_KEY") or os.environ.get("DD_API_KEY", "")
    if not api_key:
        return (
            "[Mock] Datadog API key not configured. "
            "Set DATADOG_API_KEY and DATADOG_APP_KEY environment variables.\n\n"
            "Mock data for demonstration:\n"
            f"Metric: {metric}\n"
            "Time range: last 1 hour\n"
            "Values: [p50=120ms, p95=890ms, p99=12100ms, max=14823ms]\n"
            "Trend: Sharply increasing from 08:00 UTC. "
            "Possible root cause: upstream dependency degradation."
        )

    import asyncio

    def _query():
        from datadog_api_client import ApiClient
        from datadog_api_client.v1.api.metrics_api import MetricsApi

        now_ts = int(datetime.now(timezone.utc).timestamp())
        duration_map = {"1h": 3600, "30m": 1800, "6h": 21600, "24h": 86400}
        if from_time in duration_map:
            from_ts = now_ts - duration_map[from_time]
        else:
            try:
                from_ts = int(datetime.fromisoformat(from_time).timestamp())
            except ValueError:
                from_ts = now_ts - 3600

        config = _get_dd_configuration()
        with ApiClient(config) as client:
            api = MetricsApi(client)
            response = api.query_metrics(
                _from=from_ts,
                to=now_ts if to_time == "now" else int(datetime.fromisoformat(to_time).timestamp()),
                query=metric,
            )

        if not response.series:
            return f"No data found for metric '{metric}' in the specified time range."

        series = response.series[0]
        points = series.pointlist or []
        if not points:
            return f"Metric '{metric}' has no data points in the specified time range."

        values = [p[1] for p in points if p[1] is not None]
        if not values:
            return f"Metric '{metric}' returned empty values."

        avg = sum(values) / len(values)
        max_val = max(values)
        min_val = min(values)
        return (
            f"Metric: {metric}\n"
            f"Time range: {from_time} to {to_time}\n"
            f"Data points: {len(values)}\n"
            f"  Average: {avg:.2f}\n"
            f"  Min: {min_val:.2f}\n"
            f"  Max: {max_val:.2f}\n"
            f"  Last value: {values[-1]:.2f}\n"
        )

    try:
        return await asyncio.to_thread(_query)
    except Exception as e:
        logger.exception("Datadog metrics query failed")
        return f"Error querying Datadog metrics: {e}"


@function_tool()
async def query_datadog_logs(query: str, service: str | None = None, minutes_ago: int = 30) -> str:
    """Query Datadog Log Explorer for matching log entries.

    Args:
        query: Log search query, e.g. 'error timeout' or 'status:error'
        service: Optional service name filter, e.g. 'backboard-gateway'
        minutes_ago: How far back to search (default: last 30 minutes)
    """
    api_key = os.environ.get("DATADOG_API_KEY") or os.environ.get("DD_API_KEY", "")
    if not api_key:
        # Return mock data from application_logs.json concept
        service_filter = f" for service '{service}'" if service else ""
        return (
            f"[Mock] Datadog log search{service_filter}: '{query}' (last {minutes_ago} min)\n\n"
            "Results (mock data):\n"
            "08:02:10Z [ERROR] backboard-gateway — Memory query exceeded SLA: 12100ms\n"
            "08:02:11Z [ERROR] backboard-gateway — Postgres connection pool exhausted:"
            " max_connections=20, waiting=47\n"
            "08:08:00Z [CRITICAL] backboard-gateway — All 20 Postgres connections in use"
            " for >30s. Wait queue depth: 63.\n"
            "\nTotal: 3 matching log entries"
        )

    import asyncio

    def _query():
        from datadog_api_client import ApiClient
        from datadog_api_client.v2.api.logs_api import LogsApi
        from datadog_api_client.v2.model.logs_list_request import LogsListRequest
        from datadog_api_client.v2.model.logs_list_request_page import LogsListRequestPage
        from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
        from datadog_api_client.v2.model.logs_sort import LogsSort

        filter_query = query
        if service:
            filter_query = f"service:{service} {query}"

        now = datetime.now(timezone.utc)
        from_iso = now.replace(second=0, microsecond=0)
        from_iso = from_iso.isoformat().replace("+00:00", "Z")
        from_iso = f"-{minutes_ago}m"

        config = _get_dd_configuration()
        with ApiClient(config) as client:
            api = LogsApi(client)
            request = LogsListRequest(
                filter=LogsQueryFilter(
                    query=filter_query,
                    _from=f"now-{minutes_ago}m",
                    to="now",
                ),
                sort=LogsSort.TIMESTAMP_DESCENDING,
                page=LogsListRequestPage(limit=25),
            )
            response = api.list_logs(body=request)

        if not response.data:
            return f"No logs found for query '{filter_query}' in the last {minutes_ago} minutes."

        lines = [f"Found {len(response.data)} log entries:\n"]
        for log in response.data[:20]:
            attrs = log.attributes
            ts = attrs.get("timestamp", "")
            level = attrs.get("status", "INFO").upper()
            msg = attrs.get("message", "")
            svc = attrs.get("service", "unknown")
            lines.append(f"{ts} [{level}] {svc} — {msg}")

        return _truncate("\n".join(lines))

    try:
        return await asyncio.to_thread(_query)
    except Exception as e:
        logger.exception("Datadog logs query failed")
        return f"Error querying Datadog logs: {e}"


@function_tool()
async def query_datadog_apm(service: str, minutes_ago: int = 30) -> str:
    """Query Datadog APM for trace error rate and latency for a service.

    Args:
        service: Service name in APM, e.g. 'backboard-gateway' or 'livekit-agent'
        minutes_ago: Time window to analyze (default: last 30 minutes)
    """
    api_key = os.environ.get("DATADOG_API_KEY") or os.environ.get("DD_API_KEY", "")
    if not api_key:
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
        data = mock_data.get(service, _default)
        errors_str = "\n  - ".join(data["top_errors"]) if data["top_errors"] else "None"
        if data["top_errors"]:
            errors_str = "\n  - " + errors_str
        return (
            f"[Mock] APM data for service '{service}' (last {minutes_ago} min):\n"
            f"  p99 Latency: {data['p99_ms']}ms\n"
            f"  Error Rate: {data['error_rate_pct']}%\n"
            f"  Throughput: {data['throughput_rps']} req/s\n"
            f"  Top Errors:{errors_str or ' None'}"
        )

    import asyncio

    def _query():
        from datadog_api_client import ApiClient
        from datadog_api_client.v1.api.metrics_api import MetricsApi

        # Map service names to seeded war_room.* metric prefixes
        metric_map = {
            "backboard-gateway": ("war_room.backboard.latency_p99", "war_room.backboard.error_rate", "war_room.backboard.throughput_rps"),
            "livekit-agent": ("war_room.agent.request_latency_ms", "war_room.agent.error_rate", "war_room.agent.requests_per_min"),
            "elevenlabs-tts": ("war_room.tts.latency_ms", "war_room.tts.error_rate", None),
            "speechmatics-proxy": ("war_room.stt.latency_ms", None, "war_room.stt.transcriptions_per_min"),
            "fastapi-dashboard": ("war_room.dashboard.request_latency_ms", "war_room.dashboard.error_rate", None),
            "postgres-rds": ("war_room.postgres.query_latency_ms", None, None),
        }

        tag = f"service:{service}"
        latency_metric, error_metric, throughput_metric = metric_map.get(
            service, (None, None, None)
        )

        config = _get_dd_configuration()
        results: dict[str, float] = {}
        with ApiClient(config) as client:
            api = MetricsApi(client)
            now_ts = int(datetime.now(timezone.utc).timestamp())
            from_ts = now_ts - (minutes_ago * 60)

            for metric, label in [
                (latency_metric, "p99_latency"),
                (error_metric, "error_rate"),
                (throughput_metric, "throughput"),
            ]:
                if not metric:
                    results[label] = 0.0
                    continue
                query = f"{metric}{{{tag}}}"
                try:
                    resp = api.query_metrics(_from=from_ts, to=now_ts, query=query)
                    if resp.series and resp.series[0].pointlist:
                        values = [p[1] for p in resp.series[0].pointlist if p[1] is not None]
                        results[label] = values[-1] if values else 0.0
                    else:
                        results[label] = 0.0
                except Exception:
                    results[label] = 0.0

        p99 = results.get("p99_latency", 0.0)
        error_rate = results.get("error_rate", 0.0) * 100  # stored as 0–1 fraction
        throughput = results.get("throughput", 0.0)

        return (
            f"APM data for service '{service}' (last {minutes_ago} min):\n"
            f"  p99 Latency: {p99:.0f}ms\n"
            f"  Error Rate: {error_rate:.1f}%\n"
            f"  Throughput: {throughput:.1f} req/s\n"
        )

    try:
        return await asyncio.to_thread(_query)
    except Exception as e:
        logger.exception("Datadog APM query failed")
        return f"Error querying Datadog APM for '{service}': {e}"


@function_tool()
async def get_datadog_monitors() -> str:
    """List all triggered (alerting or warning) Datadog monitors.

    Returns currently firing monitors with their names, status, and affected services.
    """
    api_key = os.environ.get("DATADOG_API_KEY") or os.environ.get("DD_API_KEY", "")
    if not api_key:
        return (
            "[Mock] Active Datadog monitors (triggered):\n\n"
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

    import asyncio

    def _query():
        from datadog_api_client import ApiClient
        from datadog_api_client.v1.api.monitors_api import MonitorsApi

        config = _get_dd_configuration()
        with ApiClient(config) as client:
            api = MonitorsApi(client)
            monitors = api.list_monitors()

        triggered = [m for m in monitors if m.overall_state in ("Alert", "Warn", "No Data")]
        if not triggered:
            return "No monitors are currently triggered."

        lines = [f"Triggered monitors ({len(triggered)} total):\n"]
        for m in triggered[:20]:
            lines.append(
                f"[{m.overall_state.upper()}] '{m.name}'\n"
                f"  Status: {m.overall_state} | Type: {m.type}\n"
                f"  Message: {(m.message or '')[:200]}\n"
            )
        return _truncate("\n".join(lines))

    try:
        return await asyncio.to_thread(_query)
    except Exception as e:
        logger.exception("Datadog monitors query failed")
        return f"Error querying Datadog monitors: {e}"
