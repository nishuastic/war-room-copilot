#!/usr/bin/env python3
"""Seed Datadog with realistic APM spans, metrics, and logs for the war-room-copilot demo.

Sends data for a 2-hour window:
  - Hour 1 (healthy baseline): normal traffic, low latency, no errors
  - Hour 2 (incident arc): gradual degradation → Postgres pool exhaustion →
    backboard timeout spike → TTS rate-limit → partial recovery

Usage:
    uv run python scripts/seed_datadog.py

Required env vars (set in .env or pass inline):
    DD_API_KEY, DD_APP_KEY, DD_SITE (e.g. datadoghq.eu)
"""

from __future__ import annotations

import logging
import os
import random
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_datadog")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SERVICES = [
    "livekit-agent",
    "backboard-gateway",
    "speechmatics-proxy",
    "elevenlabs-tts",
    "fastapi-dashboard",
]

HOSTNAMES = {
    "livekit-agent": "ecs-livekit-agent-abc123",
    "backboard-gateway": "ecs-backboard-gateway-xyz789",
    "speechmatics-proxy": "gke-speechmatics-proxy-xk2lp",
    "elevenlabs-tts": "aks-elevenlabs-tts-p7wqx",
    "fastapi-dashboard": "ecs-fastapi-dashboard-def456",
}

SOURCES = {
    "livekit-agent": "python",
    "backboard-gateway": "nodejs",
    "speechmatics-proxy": "python",
    "elevenlabs-tts": "python",
    "fastapi-dashboard": "python",
}


def check_env() -> tuple[str, str, str]:
    api_key = os.environ.get("DATADOG_API_KEY") or os.environ.get("DD_API_KEY", "")
    app_key = os.environ.get("DATADOG_APP_KEY") or os.environ.get("DD_APP_KEY", "")
    site = os.environ.get("DD_SITE", "datadoghq.com")
    if not api_key or not app_key:
        logger.error(
            "Missing API/App key. Set DD_API_KEY + DD_APP_KEY in .env and re-run."
        )
        raise SystemExit(1)
    return api_key, app_key, site


def _make_config(api_key: str, app_key: str, site: str):
    from datadog_api_client import Configuration

    config = Configuration()
    config.api_key["apiKeyAuth"] = api_key
    config.api_key["appKeyAuth"] = app_key
    config.server_variables["site"] = site
    return config


# ---------------------------------------------------------------------------
# APM spans via REST (no local agent needed)
# ---------------------------------------------------------------------------


def seed_apm_spans(api_key: str, site: str) -> None:
    """Submit APM spans directly via Datadog /api/v2/spans (no agent required)."""
    import json
    import struct
    import urllib.request

    logger.info("Seeding APM spans via REST API (no agent needed)...")

    now_ns = int(time.time() * 1e9)
    minute_ns = 60 * int(1e9)

    # Build a realistic set of traces for the incident window
    # Each trace = list of spans
    traces = []

    def make_span(
        service: str,
        resource: str,
        duration_ms: int,
        error: int = 0,
        parent_id: int = 0,
        minutes_ago: int = 0,
        extra_meta: dict | None = None,
    ) -> dict:
        span_id = random.getrandbits(63)
        trace_id = random.getrandbits(63)
        start_ns = now_ns - minutes_ago * minute_ns
        return {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_id": parent_id,
            "name": resource,
            "resource": resource,
            "service": service,
            "type": "web",
            "start": start_ns,
            "duration": duration_ms * 1_000_000,
            "error": error,
            "meta": {
                "env": "production",
                "version": "0.1.0",
                **(extra_meta or {}),
            },
            "metrics": {"_sampling_priority_v1": 1},
        }

    # ── Healthy baseline (60–120 min ago) ───────────────────────────────────
    healthy_scenarios = [
        # Normal agent request cycles
        ("livekit-agent", "agent.handle_wake_word", 320, 0, 115),
        ("livekit-agent", "agent.handle_wake_word", 290, 0, 110),
        ("livekit-agent", "agent.handle_wake_word", 340, 0, 105),
        ("backboard-gateway", "backboard.query_memory", 380, 0, 114),
        ("backboard-gateway", "backboard.query_memory", 420, 0, 109),
        ("speechmatics-proxy", "stt.transcribe", 390, 0, 113),
        ("speechmatics-proxy", "stt.transcribe", 410, 0, 108),
        ("elevenlabs-tts", "tts.synthesize", 210, 0, 112),
        ("elevenlabs-tts", "tts.synthesize", 195, 0, 107),
        ("fastapi-dashboard", "GET /api/sessions", 18, 0, 111),
        ("fastapi-dashboard", "GET /api/sessions", 22, 0, 106),
        ("fastapi-dashboard", "GET /health", 2, 0, 100),
        ("livekit-agent", "agent.skill_route", 85, 0, 95),
        ("backboard-gateway", "backboard.store_decision", 290, 0, 94),
        ("livekit-agent", "agent.handle_wake_word", 310, 0, 90),
        ("elevenlabs-tts", "tts.synthesize", 205, 0, 89),
        ("speechmatics-proxy", "stt.transcribe", 400, 0, 88),
        ("fastapi-dashboard", "GET /api/sessions/1/decisions", 31, 0, 87),
        ("backboard-gateway", "backboard.query_memory", 350, 0, 85),
        ("livekit-agent", "agent.tool_call.get_recent_commits", 540, 0, 83),
    ]

    for svc, res, dur, err, mins in healthy_scenarios:
        traces.append([make_span(svc, res, dur, err, minutes_ago=mins)])

    # ── Degradation begins (45–60 min ago) ──────────────────────────────────
    degrading = [
        ("backboard-gateway", "backboard.query_memory", 1200, 0, 58,
         {"db.pool_size": "20", "db.waiting": "5"}),
        ("backboard-gateway", "backboard.query_memory", 2800, 0, 55,
         {"db.pool_size": "20", "db.waiting": "18"}),
        ("livekit-agent", "agent.handle_wake_word", 3200, 0, 54, {}),
        ("speechmatics-proxy", "stt.transcribe", 850, 0, 52, {}),
        ("backboard-gateway", "backboard.query_memory", 5900, 1, 50,
         {"error.type": "SlowQueryWarning", "db.waiting": "32",
          "error.msg": "Query took 5900ms — pool approaching exhaustion"}),
        ("elevenlabs-tts", "tts.synthesize", 310, 0, 49, {"tts.quota_pct": "72"}),
        ("fastapi-dashboard", "GET /api/sessions", 45, 0, 48, {}),
    ]

    for svc, res, dur, err, mins, meta in degrading:
        traces.append([make_span(svc, res, dur, err, minutes_ago=mins, extra_meta=meta)])

    # ── Full incident (20–45 min ago) ────────────────────────────────────────
    incident = [
        ("backboard-gateway", "backboard.query_memory", 12100, 1, 44,
         {"error.type": "TimeoutError",
          "error.msg": "Upstream response exceeded 12s threshold",
          "db.active_connections": "100", "db.waiting": "47",
          "http.status_code": "504"}),
        ("livekit-agent", "agent.handle_wake_word", 14823, 1, 43,
         {"error.type": "ToolError",
          "error.msg": "backboard-gateway returned 504 after 12.1s"}),
        ("speechmatics-proxy", "stt.transcribe", 2800, 0, 42,
         {"stt.replicas": "1", "stt.note": "OOMKilled replica, single pod handling 2x load"}),
        ("elevenlabs-tts", "tts.synthesize", 890, 1, 40,
         {"error.type": "RateLimitError",
          "error.msg": "429 Too Many Requests — daily quota exhausted",
          "tts.quota_pct": "100", "http.status_code": "429"}),
        ("elevenlabs-tts", "tts.synthesize", 780, 1, 38,
         {"error.type": "RateLimitError", "error.msg": "429 — quota exhausted"}),
        ("backboard-gateway", "backboard.query_memory", 12400, 1, 37,
         {"error.type": "TimeoutError", "db.waiting": "63"}),
        ("livekit-agent", "agent.handle_wake_word", 13900, 1, 36,
         {"error.type": "ToolError", "error.msg": "backboard-gateway timeout"}),
        ("fastapi-dashboard", "GET /api/sessions", 38, 0, 35, {}),
        ("fastapi-dashboard", "GET /health", 3, 0, 30, {}),
        ("backboard-gateway", "backboard.query_memory", 11900, 1, 28,
         {"error.type": "TimeoutError", "db.waiting": "71"}),
        ("speechmatics-proxy", "stt.transcribe", 2750, 0, 25, {}),
        ("livekit-agent", "agent.tool_call.query_datadog_apm", 1200, 0, 22,
         {"tool": "query_datadog_apm", "tool.service": "backboard-gateway"}),
        ("livekit-agent", "agent.tool_call.search_runbook", 45, 0, 21,
         {"tool": "search_runbook", "tool.keywords": "connection pool postgres"}),
    ]

    for svc, res, dur, err, mins, meta in incident:
        traces.append([make_span(svc, res, dur, err, minutes_ago=mins, extra_meta=meta)])

    # ── Partial recovery (0–20 min ago) ─────────────────────────────────────
    recovery = [
        ("backboard-gateway", "backboard.query_memory", 3200, 0, 18,
         {"db.note": "PgBouncer deployed, connections stabilising"}),
        ("backboard-gateway", "backboard.query_memory", 1800, 0, 15, {}),
        ("livekit-agent", "agent.handle_wake_word", 4200, 0, 14, {}),
        ("speechmatics-proxy", "stt.transcribe", 2600, 0, 12, {}),
        ("backboard-gateway", "backboard.query_memory", 980, 0, 10, {}),
        ("livekit-agent", "agent.handle_wake_word", 1400, 0, 8, {}),
        ("fastapi-dashboard", "GET /api/sessions", 25, 0, 5, {}),
        ("fastapi-dashboard", "GET /health", 2, 0, 3, {}),
        ("backboard-gateway", "backboard.query_memory", 540, 0, 2, {}),
        ("livekit-agent", "agent.handle_wake_word", 620, 0, 1, {}),
    ]

    for svc, res, dur, err, mins, meta in recovery:
        traces.append([make_span(svc, res, dur, err, minutes_ago=mins, extra_meta=meta)])

    # Send via msgpack to /api/v2/spans
    try:
        import msgpack  # type: ignore[import-untyped]

        payload = msgpack.packb(traces, use_bin_type=True)
        host = f"https://trace.agent.{site}"
        req = urllib.request.Request(
            f"{host}/api/v2/spans",
            data=payload,
            headers={
                "DD-API-KEY": api_key,
                "Content-Type": "application/msgpack",
            },
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            logger.info(
                "APM spans submitted via REST: %d traces, HTTP %d",
                len(traces),
                resp.status,
            )
    except ImportError:
        # Fall back to JSON if msgpack not available
        import json

        payload_json = json.dumps(traces).encode()
        host = f"https://trace.agent.{site}"
        req = urllib.request.Request(
            f"{host}/api/v2/spans",
            data=payload_json,
            headers={
                "DD-API-KEY": api_key,
                "Content-Type": "application/json",
            },
            method="PUT",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                logger.info("APM spans submitted (JSON fallback): %d traces", len(traces))
        except Exception as e:
            logger.warning("APM span submission failed: %s — skipping APM", e)
    except Exception as e:
        logger.warning("APM span submission failed: %s — skipping APM", e)


# ---------------------------------------------------------------------------
# Metrics — rich time series with healthy baseline + incident arc
# ---------------------------------------------------------------------------


def seed_metrics(api_key: str, app_key: str, site: str) -> None:
    """Push 24 metric series covering a 2-hour healthy→incident→recovery window."""
    logger.info("Seeding metrics (2h window, 5-min resolution)...")

    from datadog_api_client import ApiClient, Configuration
    from datadog_api_client.v2.api.metrics_api import MetricsApi
    from datadog_api_client.v2.model.metric_intake_type import MetricIntakeType
    from datadog_api_client.v2.model.metric_payload import MetricPayload
    from datadog_api_client.v2.model.metric_point import MetricPoint
    from datadog_api_client.v2.model.metric_series import MetricSeries

    config = _make_config(api_key, app_key, site)
    now = int(time.time())

    # 24 points = 2 hours at 5-min intervals
    def pts(values: list[float]) -> list[MetricPoint]:
        return [
            MetricPoint(timestamp=now - (len(values) - 1 - i) * 300, value=v)
            for i, v in enumerate(values)
        ]

    def s(name: str, values: list[float], tags: list[str]) -> MetricSeries:
        return MetricSeries(
            metric=name,
            type=MetricIntakeType.GAUGE,
            points=pts(values),
            tags=tags,
        )

    # ── Healthy baseline (first 12 pts) then incident (next 8) then recovery (last 4)
    # Pattern: [H H H H H H H H H H H H | D D D D I I I I | R R R R]
    # H=healthy, D=degrading, I=incident, R=recovering

    series = [
        # ── livekit-agent ──────────────────────────────────────────────────
        s("war_room.agent.request_latency_ms",
          [310, 295, 320, 305, 315, 290, 330, 300, 285, 320, 310, 295,
           890, 2100, 4200, 8900, 14823, 13900, 14200, 12800,
           4200, 1800, 820, 620],
          ["service:livekit-agent", "env:production"]),
        s("war_room.agent.requests_per_min",
          [4.2, 3.8, 4.5, 4.1, 4.8, 3.9, 4.3, 4.6, 3.7, 4.4, 4.0, 4.2,
           3.1, 2.4, 1.8, 1.2, 0.8, 0.9, 1.0, 1.1,
           2.8, 3.4, 3.9, 4.1],
          ["service:livekit-agent", "env:production"]),
        s("war_room.agent.error_rate",
          [0.0, 0.0, 0.0, 0.0, 0.0, 0.01, 0.0, 0.0, 0.0, 0.01, 0.0, 0.0,
           0.05, 0.18, 0.32, 0.67, 1.0, 1.0, 0.95, 0.88,
           0.42, 0.15, 0.03, 0.01],
          ["service:livekit-agent", "env:production"]),
        s("war_room.agent.wake_words_per_min",
          [1.2, 0.8, 1.4, 1.1, 1.3, 0.9, 1.5, 1.0, 0.7, 1.2, 1.1, 1.3,
           0.9, 0.6, 0.4, 0.2, 0.1, 0.1, 0.2, 0.3,
           0.7, 1.0, 1.2, 1.3],
          ["service:livekit-agent", "env:production"]),

        # ── backboard-gateway ──────────────────────────────────────────────
        s("war_room.backboard.latency_p99",
          [420, 380, 450, 410, 430, 395, 440, 415, 390, 425, 405, 435,
           1200, 2800, 5900, 9400, 12100, 12400, 11900, 12300,
           3200, 1800, 980, 540],
          ["service:backboard-gateway", "env:production"]),
        s("war_room.backboard.latency_p50",
          [210, 195, 225, 205, 215, 200, 220, 208, 192, 218, 202, 212,
           580, 1100, 2400, 4200, 6800, 7100, 6500, 6900,
           1400, 820, 480, 290],
          ["service:backboard-gateway", "env:production"]),
        s("war_room.backboard.error_rate",
          [0.0, 0.0, 0.01, 0.0, 0.0, 0.0, 0.01, 0.0, 0.0, 0.0, 0.01, 0.0,
           0.05, 0.18, 0.34, 0.52, 0.88, 0.92, 0.85, 0.89,
           0.44, 0.18, 0.04, 0.01],
          ["service:backboard-gateway", "env:production"]),
        s("war_room.backboard.throughput_rps",
          [2.8, 2.5, 3.1, 2.7, 2.9, 2.6, 3.0, 2.8, 2.4, 2.9, 2.7, 2.8,
           2.1, 1.6, 1.2, 0.8, 0.4, 0.3, 0.4, 0.5,
           1.2, 1.8, 2.2, 2.5],
          ["service:backboard-gateway", "env:production"]),

        # ── postgres-rds ───────────────────────────────────────────────────
        s("war_room.postgres.active_connections",
          [14, 12, 16, 13, 15, 11, 17, 14, 12, 15, 13, 14,
           28, 45, 68, 85, 100, 100, 100, 100,
           82, 58, 34, 22],
          ["service:postgres-rds", "env:production"]),
        s("war_room.postgres.wait_queue_depth",
          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
           2, 8, 22, 38, 63, 71, 68, 65,
           32, 14, 4, 0],
          ["service:postgres-rds", "env:production"]),
        s("war_room.postgres.query_latency_ms",
          [12, 11, 14, 12, 13, 11, 15, 12, 11, 13, 12, 13,
           180, 820, 2400, 4500, 8900, 9100, 8700, 8800,
           2100, 890, 280, 45],
          ["service:postgres-rds", "env:production"]),
        s("war_room.postgres.deadlocks",
          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
           0, 1, 3, 8, 14, 18, 16, 15,
           6, 2, 0, 0],
          ["service:postgres-rds", "env:production"]),

        # ── elevenlabs-tts ─────────────────────────────────────────────────
        s("war_room.tts.quota_used_pct",
          [8, 12, 16, 21, 26, 31, 37, 43, 50, 58, 66, 74,
           80, 85, 90, 94, 97, 98.4, 100, 100,
           100, 100, 100, 100],
          ["service:elevenlabs-tts", "env:production"]),
        s("war_room.tts.error_rate",
          [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.01, 0.0,
           0.0, 0.02, 0.08, 0.24, 0.65, 1.0, 1.0, 1.0,
           1.0, 1.0, 1.0, 1.0],
          ["service:elevenlabs-tts", "env:production"]),
        s("war_room.tts.latency_ms",
          [195, 182, 210, 198, 205, 188, 215, 200, 185, 208, 196, 202,
           245, 310, 420, 580, 890, 820, 870, 850,
           None, None, None, None],  # null = no successful requests
          ["service:elevenlabs-tts", "env:production"]),

        # ── speechmatics-proxy ─────────────────────────────────────────────
        s("war_room.stt.latency_ms",
          [385, 402, 375, 415, 390, 408, 378, 420, 365, 398, 388, 405,
           620, 980, 1800, 2400, 2800, 2750, 2800, 2760,
           2700, 2650, 2580, 2400],
          ["service:speechmatics-proxy", "env:production"]),
        s("war_room.stt.pod_restarts",
          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
           0, 1, 2, 3, 4, 4, 4, 4,
           4, 4, 4, 4],
          ["service:speechmatics-proxy", "env:production"]),
        s("war_room.stt.memory_usage_mib",
          [210, 218, 225, 232, 240, 248, 258, 270, 285, 310, 340, 385,
           420, 460, 498, 510, None, 180, 220, 280,
           320, 360, 390, 410],
          ["service:speechmatics-proxy", "env:production"]),
        s("war_room.stt.transcriptions_per_min",
          [8.2, 7.9, 8.5, 8.1, 8.4, 7.8, 8.6, 8.0, 7.7, 8.3, 8.1, 8.2,
           6.4, 5.2, 4.1, 3.2, 2.8, 2.9, 3.0, 3.1,
           3.8, 4.5, 5.6, 6.8],
          ["service:speechmatics-proxy", "env:production"]),

        # ── fastapi-dashboard ──────────────────────────────────────────────
        s("war_room.dashboard.request_latency_ms",
          [18, 15, 22, 19, 20, 16, 24, 18, 14, 21, 17, 19,
           25, 32, 28, 35, 42, 38, 40, 36,
           22, 18, 16, 15],
          ["service:fastapi-dashboard", "env:production"]),
        s("war_room.dashboard.error_rate",
          [0.0] * 24,
          ["service:fastapi-dashboard", "env:production"]),

        # ── system-level ───────────────────────────────────────────────────
        s("war_room.system.active_sessions",
          [2, 2, 3, 2, 3, 2, 3, 3, 2, 3, 2, 2,
           2, 2, 1, 1, 1, 1, 1, 1,
           2, 2, 3, 3],
          ["env:production"]),
        s("war_room.system.decisions_captured",
          [3, 4, 3, 5, 4, 3, 5, 4, 3, 4, 5, 4,
           2, 2, 1, 1, 0, 0, 0, 1,
           3, 4, 5, 4],
          ["env:production"]),
        s("war_room.system.tool_calls_per_min",
          [1.2, 0.9, 1.4, 1.1, 1.3, 0.8, 1.5, 1.0, 0.7, 1.2, 1.1, 1.3,
           0.8, 0.5, 0.4, 0.3, 0.1, 0.1, 0.2, 0.4,
           0.9, 1.1, 1.3, 1.4],
          ["env:production"]),
    ]

    # Filter out any None values from points
    clean_series = []
    for serie in series:
        clean_pts = [p for p in serie.points if p.value is not None]
        if clean_pts:
            serie.points = clean_pts
            clean_series.append(serie)

    config = _make_config(api_key, app_key, site)
    with ApiClient(config) as client:
        api = MetricsApi(client)
        api.submit_metrics(body=MetricPayload(series=clean_series))

    logger.info("Pushed %d metric series to Datadog.", len(clean_series))


# ---------------------------------------------------------------------------
# Logs — full lifecycle: INFO baseline + WARNING degradation + ERROR/CRITICAL incident
# ---------------------------------------------------------------------------


def seed_logs(api_key: str, app_key: str, site: str) -> None:
    """Push ~40 log entries covering healthy, degrading, incident, and recovery phases."""
    logger.info("Seeding log entries (healthy baseline + incident arc)...")

    from datadog_api_client import ApiClient, Configuration
    from datadog_api_client.v2.api.logs_api import LogsApi
    from datadog_api_client.v2.model.http_log import HTTPLog
    from datadog_api_client.v2.model.http_log_item import HTTPLogItem

    config = _make_config(api_key, app_key, site)

    logs = [
        # ── Healthy baseline INFO logs ────────────────────────────────────
        ("livekit-agent", "info",
         "Session room_inc_20260301_01 started. 3 participants detected.",
         "env:production,phase:healthy", 118),
        ("livekit-agent", "info",
         "Backboard long-term memory loaded 3 past decisions for context injection.",
         "env:production,phase:healthy", 115),
        ("backboard-gateway", "info",
         "Memory query completed in 420ms for assistant asst_backboard_prod_01.",
         "env:production,phase:healthy", 114),
        ("speechmatics-proxy", "info",
         "WebSocket transcription session opened. Diarization enabled, 3 speakers.",
         "env:production,phase:healthy", 113),
        ("elevenlabs-tts", "info",
         "TTS synthesis complete: 218 chars in 195ms. Daily quota: 8% used.",
         "env:production,phase:healthy", 112),
        ("fastapi-dashboard", "info",
         "GET /api/sessions 200 OK (18ms). Client: 10.0.1.42",
         "env:production,phase:healthy", 111),
        ("livekit-agent", "info",
         "Wake word 'sam' detected. Skill routed: INVESTIGATE (confidence=0.84).",
         "env:production,phase:healthy", 108),
        ("livekit-agent", "info",
         "Tool call: get_recent_commits completed in 542ms.",
         "env:production,phase:healthy", 107),
        ("backboard-gateway", "info",
         "Decision stored: 'team agreed to use feature flags for gradual rollout'.",
         "env:production,phase:healthy", 105),
        ("elevenlabs-tts", "info",
         "TTS synthesis complete: 342 chars in 210ms. Daily quota: 21% used.",
         "env:production,phase:healthy", 100),
        ("fastapi-dashboard", "info",
         "WebSocket /api/stream connected. Streaming session room_inc_20260301_01.",
         "env:production,phase:healthy", 98),
        ("livekit-agent", "info",
         "Session room_inc_20260301_02 started. 2 participants.",
         "env:production,phase:healthy", 95),
        ("speechmatics-proxy", "info",
         "Speaker voiceprint captured for S1 in session room_inc_20260301_01.",
         "env:production,phase:healthy", 92),
        ("backboard-gateway", "info",
         "Memory query completed in 395ms. Cache hit ratio: 0.72.",
         "env:production,phase:healthy", 90),

        # ── Degradation warnings ──────────────────────────────────────────
        ("postgres-rds", "warning",
         "Connection count reaching 60% of max_connections (60/100). Monitor closely.",
         "env:production,phase:degrading", 72),
        ("backboard-gateway", "warning",
         "Memory query latency elevated: 1200ms (p99). Threshold: 500ms.",
         "env:production,phase:degrading", 68),
        ("speechmatics-proxy", "warning",
         "Memory usage at 420Mi / 512Mi limit (82%). OOM risk increasing.",
         "env:production,phase:degrading", 65),
        ("backboard-gateway", "warning",
         "Memory query latency at 2800ms. Postgres pool at 68% utilisation.",
         "env:production,phase:degrading", 62),
        ("elevenlabs-tts", "warning",
         "Daily TTS quota at 80% (80000/100000 chars). Rate limiting may occur soon.",
         "env:production,phase:degrading", 60),
        ("postgres-rds", "warning",
         "Slow query detected: SELECT * FROM memory_entries took 2400ms.",
         "env:production,phase:degrading", 58),
        ("livekit-agent", "warning",
         "Backboard response taking >3s — skill routing degraded. Using cached context.",
         "env:production,phase:degrading", 55),

        # ── Incident errors / criticals ───────────────────────────────────
        ("speechmatics-proxy", "critical",
         "OOMKilled: container exceeded 512Mi memory limit (restart #1). "
         "Audio buffer: 45MB in-flight.",
         "env:production,phase:incident,cluster:war-room-gke-prod", 63),
        ("speechmatics-proxy", "critical",
         "OOMKilled again (restart #4). Running on 1/2 replicas. "
         "Surviving pod handling 2x load.",
         "env:production,phase:incident,cluster:war-room-gke-prod", 55),
        ("postgres-rds", "critical",
         "FATAL: remaining connection slots reserved for superuser. "
         "max_connections=100 reached. New queries will fail.",
         "env:production,phase:incident", 50),
        ("backboard-gateway", "error",
         "Memory query exceeded SLA: 12100ms (threshold: 5000ms). "
         "Postgres pool exhausted.",
         "env:production,phase:incident", 48),
        ("backboard-gateway", "critical",
         "All 100 Postgres connections in use for >30s. "
         "Wait queue depth: 63. New requests failing.",
         "env:production,phase:incident", 47),
        ("livekit-agent", "error",
         "Tool call failed: backboard-gateway returned 504 after 12.1s. "
         "Agent operating without memory context.",
         "env:production,phase:incident", 46),
        ("elevenlabs-tts", "error",
         "429 Too Many Requests. Daily quota exhausted (100%). "
         "Retry-After: 3600s. Agent will be silent.",
         "env:production,phase:incident", 44),
        ("elevenlabs-tts", "error",
         "TTS synthesis failed for session room_inc_20260301_01. "
         "No fallback TTS provider configured.",
         "env:production,phase:incident", 43),
        ("livekit-agent", "error",
         "Wake word detected but agent cannot speak — TTS rate limited. "
         "Skill: INVESTIGATE routed silently to dashboard.",
         "env:production,phase:incident", 40),
        ("backboard-gateway", "error",
         "Memory query exceeded SLA: 12400ms. Redis cache also unreachable "
         "(ECONNREFUSED :6379). No fallback.",
         "env:production,phase:incident", 38),
        ("postgres-rds", "critical",
         "Deadlock detected between 14 concurrent INSERT operations. "
         "Killing oldest idle transactions.",
         "env:production,phase:incident", 35),

        # ── Recovery ──────────────────────────────────────────────────────
        ("backboard-gateway", "info",
         "PgBouncer deployed. Postgres active connections dropping: 82 → 58.",
         "env:production,phase:recovery", 18),
        ("postgres-rds", "info",
         "Connection pool stabilising. Active: 34/100, waiting: 0.",
         "env:production,phase:recovery", 14),
        ("backboard-gateway", "info",
         "Memory query latency recovering: p99 now 980ms (was 12100ms).",
         "env:production,phase:recovery", 10),
        ("livekit-agent", "info",
         "Backboard memory available again. Reloading session context.",
         "env:production,phase:recovery", 8),
        ("speechmatics-proxy", "info",
         "Second replica restarted and healthy. Latency improving: 2400ms.",
         "env:production,phase:recovery", 6),
        ("fastapi-dashboard", "info",
         "All health checks passing. Dashboard reporting 2 active sessions.",
         "env:production,phase:recovery", 4),
        ("livekit-agent", "info",
         "Agent fully operational. Wake word detected: INVESTIGATE (confidence=0.81).",
         "env:production,phase:recovery", 2),
    ]

    items = []
    for svc, status, message, tags, _mins_ago in logs:
        items.append(HTTPLogItem(
            message=message,
            service=svc,
            status=status,
            ddsource=SOURCES.get(svc, "python"),
            ddtags=f"{tags},service:{svc}",
            hostname=HOSTNAMES.get(svc, "unknown"),
        ))

    with ApiClient(config) as client:
        api = LogsApi(client)
        # Send in batches of 10 to avoid payload limits
        for i in range(0, len(items), 10):
            batch = items[i : i + 10]
            api.submit_log(body=HTTPLog(batch))
            logger.info("  Sent log batch %d–%d", i + 1, i + len(batch))

    logger.info("Pushed %d log entries to Datadog.", len(items))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    api_key, app_key, site = check_env()

    logger.info("=" * 60)
    logger.info("War Room Copilot — Datadog Data Seeder")
    logger.info("Site: %s  |  2-hour window (healthy → incident → recovery)", site)
    logger.info("=" * 60)

    seed_apm_spans(api_key, site)
    seed_metrics(api_key, app_key, site)
    seed_logs(api_key, app_key, site)

    base = f"https://app.{site}"
    logger.info("=" * 60)
    logger.info("Done! View in Datadog (%s):", site)
    logger.info("  Metrics:  %s/metric/explorer  → search 'war_room'", base)
    logger.info("  Logs:     %s/logs             → filter service:livekit-agent", base)
    logger.info("  APM:      %s/apm/traces       → filter service:backboard-gateway", base)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
