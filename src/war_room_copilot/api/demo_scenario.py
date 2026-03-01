"""Scripted incident scenario for hackathon demo mode.

Populates the shared state dict on a schedule so the SSE stream picks up
events gradually — simulating a real war room incident without LiveKit.

Scenario: SEV-1 checkout service returning 503s due to DB connection pool
exhaustion after a bad index migration.  Four speakers, all six agent
skills activated, contradiction detected, decisions captured.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger("war-room-copilot.demo")

# ── Speakers ────────────────────────────────────────────────────────────────

SPEAKERS: list[dict[str, Any]] = [
    {"id": 1, "name": "Sarah Chen", "role": "Incident Commander", "colorVar": "--speaker-1"},
    {"id": 2, "name": "Marcus Johnson", "role": "SRE", "colorVar": "--speaker-2"},
    {"id": 3, "name": "Priya Patel", "role": "Backend Engineer", "colorVar": "--speaker-3"},
    {"id": 4, "name": "Alex Kim", "role": "DBA", "colorVar": "--speaker-4"},
]

# ── Scripted events ─────────────────────────────────────────────────────────
# Each tuple: (delay_seconds, event_type, data)
# delay is relative to the *previous* event, not absolute.

ScriptEntry = tuple[float, str, dict[str, Any]]


def _build_script() -> list[ScriptEntry]:
    """Build the timed event script.  Epochs are filled at runtime."""
    return [
        # ── Opening: incident declared ────────────────────────────────
        (0.5, "speaker", SPEAKERS[0]),
        (0.3, "speaker", SPEAKERS[1]),
        (0.3, "speaker", SPEAKERS[2]),
        (0.3, "speaker", SPEAKERS[3]),
        (0.5, "orb", {"state": "listening"}),
        (1.0, "transcript", {
            "speaker": "Sarah Chen",
            "text": "Alright everyone, this is a SEV-1. Checkout service is returning 503s "
                    "across all regions. Customer impact confirmed — about 15% of transactions failing.",
        }),
        (0.5, "timeline", {
            "type": "transcript",
            "description": "SEV-1 declared: checkout 503s across all regions",
        }),
        (2.0, "transcript", {
            "speaker": "Marcus Johnson",
            "text": "I'm seeing connection pool exhaustion on the primary DB cluster. "
                    "Active connections spiked from 200 to 2,000 about 20 minutes ago.",
        }),
        (1.5, "transcript", {
            "speaker": "Priya Patel",
            "text": "We deployed checkout-service v2.14.3 about an hour ago. "
                    "Could be related to the new query optimization PR.",
        }),
        # ── Agent investigates (skill: investigate → github) ──────────
        (1.0, "orb", {"state": "thinking"}),
        (0.5, "transcript", {
            "speaker": "War Room Copilot",
            "text": "I'm investigating the recent deploy and checking GitHub for related changes.",
        }),
        (0.8, "graph_trace", {
            "node": "skill_router",
            "query": "checkout 503 connection pool exhaustion after deploy",
            "duration": 0.3,
        }),
        (0.5, "timeline", {
            "type": "tool_call",
            "description": "Agent routing: investigate skill selected",
        }),
        (1.2, "graph_trace", {
            "node": "investigate",
            "query": "checkout-service v2.14.3 connection pool changes",
            "duration": 2.1,
        }),
        (0.3, "graph_trace", {
            "node": "github",
            "query": "search_code: connection pool configuration",
            "duration": 1.5,
        }),
        (0.5, "finding", {
            "text": "PR #892 merged 2 hours ago: 'Optimize checkout queries' — "
                    "removes compound index on orders(user_id, created_at) "
                    "and replaces with sequential scans",
            "source": "github",
        }),
        (0.3, "timeline", {
            "type": "finding",
            "description": "PR #892 removed compound index on orders table",
        }),
        (1.0, "finding", {
            "text": "Issue #1247 (open): 'Connection pool exhaustion under load' — "
                    "reported 3 weeks ago with suggested fix to increase pool_max_size",
            "source": "github",
        }),
        (0.5, "orb", {"state": "speaking"}),
        (1.0, "transcript", {
            "speaker": "War Room Copilot",
            "text": "I found that PR #892 removed a compound index on the orders table. "
                    "Without that index, checkout queries are doing sequential scans, "
                    "which would explain the connection pool exhaustion. "
                    "There's also Issue #1247 about pool exhaustion under load.",
        }),
        (0.5, "orb", {"state": "listening"}),
        # ── Team discussion ───────────────────────────────────────────
        (2.0, "transcript", {
            "speaker": "Alex Kim",
            "text": "That makes sense. Without the compound index, each checkout query "
                    "holds a connection 10x longer. The pool fills up and new requests get 503s.",
        }),
        (2.0, "transcript", {
            "speaker": "Marcus Johnson",
            "text": "I'm seeing p99 latency at 12 seconds, normally it's under 200ms. "
                    "Error rate is at 15% and climbing.",
        }),
        (0.5, "finding", {
            "text": "Metrics: p99 latency 12s (baseline 200ms), error rate 15%, "
                    "DB active connections 2,000/2,000 (pool saturated)",
            "source": "metrics",
        }),
        (0.3, "timeline", {
            "type": "finding",
            "description": "Metrics confirm: p99 12s, error rate 15%, pool saturated",
        }),
        (1.5, "transcript", {
            "speaker": "Priya Patel",
            "text": "Wait, I think the deploy was actually 3 hours ago, not 1 hour. "
                    "Let me check the deploy pipeline.",
        }),
        # ── Agent detects contradiction (skill: contradict) ───────────
        (1.0, "orb", {"state": "thinking"}),
        (0.8, "graph_trace", {
            "node": "skill_router",
            "query": "contradiction: deploy timing mismatch",
            "duration": 0.2,
        }),
        (1.0, "graph_trace", {
            "node": "contradict",
            "query": "Priya said deploy was 1 hour ago, now says 3 hours ago",
            "duration": 1.8,
        }),
        (0.5, "timeline", {
            "type": "contradiction",
            "description": "Deploy timing mismatch: 1 hour vs 3 hours ago",
        }),
        (0.5, "orb", {"state": "speaking"}),
        (1.0, "transcript", {
            "speaker": "War Room Copilot",
            "text": "Contradiction detected: Priya, you initially said the deploy was "
                    "'about an hour ago' but now you're saying 3 hours. "
                    "The GitHub deploy log shows v2.14.3 was deployed at 14:32 UTC — "
                    "that's 2 hours and 47 minutes ago. This matters because the "
                    "connection pool issue started 20 minutes ago, not at deploy time.",
        }),
        (0.5, "orb", {"state": "listening"}),
        # ── Key realization ───────────────────────────────────────────
        (2.0, "transcript", {
            "speaker": "Alex Kim",
            "text": "So the deploy was almost 3 hours ago but the pool exhaustion only "
                    "started 20 minutes ago? That means something else triggered it. "
                    "The missing index was a ticking time bomb — but what set it off?",
        }),
        # ── Agent recalls (skill: recall) ─────────────────────────────
        (1.0, "orb", {"state": "thinking"}),
        (0.8, "graph_trace", {
            "node": "skill_router",
            "query": "what triggered pool exhaustion 20 minutes ago",
            "duration": 0.2,
        }),
        (1.2, "graph_trace", {
            "node": "recall",
            "query": "cron jobs, batch processes, traffic spikes in last 30 minutes",
            "duration": 1.4,
        }),
        (0.5, "finding", {
            "text": "Cron job 'nightly-order-reconciliation' runs at 16:00 UTC daily — "
                    "started 22 minutes ago, generates 500+ concurrent checkout queries",
            "source": "code",
        }),
        (0.3, "timeline", {
            "type": "finding",
            "description": "Cron job 'nightly-order-reconciliation' triggered pool exhaustion",
        }),
        (0.5, "orb", {"state": "speaking"}),
        (1.0, "transcript", {
            "speaker": "War Room Copilot",
            "text": "Found the trigger: the nightly-order-reconciliation cron job started "
                    "22 minutes ago. It generates 500+ concurrent checkout queries. "
                    "Without the compound index from PR #892, each query holds connections "
                    "much longer — the cron job pushed the pool past its limit.",
        }),
        (0.5, "orb", {"state": "listening"}),
        # ── Decision making ───────────────────────────────────────────
        (2.0, "transcript", {
            "speaker": "Sarah Chen",
            "text": "Good work. Here's what we're going to do: First, kill the cron job "
                    "immediately to stop the bleeding. Second, push an emergency index "
                    "migration to restore the compound index. Third, bump the connection "
                    "pool from 2,000 to 3,000 as a safety margin.",
        }),
        # ── Agent captures decisions (skill: capture_decision) ────────
        (1.0, "orb", {"state": "thinking"}),
        (0.8, "graph_trace", {
            "node": "skill_router",
            "query": "decision: remediation plan",
            "duration": 0.2,
        }),
        (1.0, "graph_trace", {
            "node": "respond",
            "query": "capture three remediation decisions from Sarah",
            "duration": 0.8,
        }),
        (0.5, "decision", {
            "text": "Kill nightly-order-reconciliation cron job immediately",
            "speaker": "Sarah Chen",
        }),
        (0.3, "timeline", {
            "type": "decision",
            "description": "Decision: Kill cron job immediately",
        }),
        (0.5, "decision", {
            "text": "Push emergency index migration to restore orders(user_id, created_at) compound index",
            "speaker": "Sarah Chen",
        }),
        (0.3, "timeline", {
            "type": "decision",
            "description": "Decision: Restore compound index via emergency migration",
        }),
        (0.5, "decision", {
            "text": "Bump DB connection pool from 2,000 to 3,000 as safety margin",
            "speaker": "Sarah Chen",
        }),
        (0.3, "timeline", {
            "type": "decision",
            "description": "Decision: Increase connection pool to 3,000",
        }),
        (0.5, "orb", {"state": "speaking"}),
        (1.0, "transcript", {
            "speaker": "War Room Copilot",
            "text": "Decision captured: Three action items logged. "
                    "1) Kill cron job, 2) Restore compound index, 3) Bump pool to 3,000. "
                    "Sarah, can you confirm these are correct?",
        }),
        (0.5, "orb", {"state": "listening"}),
        (1.5, "transcript", {
            "speaker": "Sarah Chen",
            "text": "Confirmed. Marcus, kill the cron job. Priya, start the index migration. "
                    "Alex, bump the pool config.",
        }),
        # ── Remediation in progress ───────────────────────────────────
        (2.5, "transcript", {
            "speaker": "Marcus Johnson",
            "text": "Cron job killed. Active connections already dropping — down to 1,400.",
        }),
        (2.0, "transcript", {
            "speaker": "Priya Patel",
            "text": "Index migration deployed. It'll take about 5 minutes to build "
                    "on the primary.",
        }),
        (1.5, "transcript", {
            "speaker": "Alex Kim",
            "text": "Pool bumped to 3,000. Config pushed to all regions.",
        }),
        (0.5, "finding", {
            "text": "3 similar incidents in last 6 months — all triggered by batch jobs "
                    "after index changes. Suggests need for index-aware load testing.",
            "source": "metrics",
        }),
        # ── Agent summarizes (skill: summarize) ──────────────────────
        (1.5, "orb", {"state": "thinking"}),
        (0.8, "graph_trace", {
            "node": "skill_router",
            "query": "summarize incident status",
            "duration": 0.2,
        }),
        (1.5, "graph_trace", {
            "node": "summarize",
            "query": "incident summary: root cause, impact, remediation status",
            "duration": 2.0,
        }),
        (0.5, "orb", {"state": "speaking"}),
        (1.0, "transcript", {
            "speaker": "War Room Copilot",
            "text": "Incident summary: Root cause was PR #892 removing a compound index, "
                    "triggered by the nightly cron job generating 500+ queries. "
                    "Impact: 15% checkout failures for ~20 minutes. "
                    "All three remediation actions are in progress. "
                    "I also found 3 similar incidents in the last 6 months — "
                    "suggesting we need index-aware load testing in CI.",
        }),
        (0.5, "orb", {"state": "listening"}),
        # ── Recovery confirmed ────────────────────────────────────────
        (3.0, "transcript", {
            "speaker": "Marcus Johnson",
            "text": "Error rate dropping fast — down to 2%. p99 back to 400ms. "
                    "Connections at 350. We're recovering.",
        }),
        (2.0, "transcript", {
            "speaker": "Sarah Chen",
            "text": "Great work everyone. Let's keep monitoring for 30 minutes "
                    "then we can close this out. Copilot, can you draft a post-mortem?",
        }),
        # ── Agent postmortem (skill: postmortem) ──────────────────────
        (1.0, "orb", {"state": "thinking"}),
        (0.8, "graph_trace", {
            "node": "skill_router",
            "query": "generate post-mortem report",
            "duration": 0.2,
        }),
        (2.0, "graph_trace", {
            "node": "postmortem",
            "query": "structured post-mortem: checkout SEV-1 connection pool exhaustion",
            "duration": 3.5,
        }),
        (0.5, "orb", {"state": "speaking"}),
        (1.0, "transcript", {
            "speaker": "War Room Copilot",
            "text": "Post-mortem drafted and saved. Summary: SEV-1 checkout outage caused by "
                    "compound index removal in PR #892, triggered by nightly batch job. "
                    "MTTR: 23 minutes. Action items: add index-aware load tests, "
                    "implement cron job connection limits, add pool exhaustion alerting. "
                    "I'll send the full report to the incident channel.",
        }),
        (0.5, "orb", {"state": "idle"}),
        (0.5, "timeline", {
            "type": "finding",
            "description": "Post-mortem generated and saved",
        }),
        (2.0, "transcript", {
            "speaker": "Sarah Chen",
            "text": "Perfect. Error rate is at 0.1% now — back to baseline. "
                    "I'm downgrading to SEV-3 for monitoring. Thanks everyone.",
        }),
    ]


async def run_demo_scenario(state: dict[str, Any]) -> None:
    """Populate *state* with timed events matching the scripted scenario.

    This function runs as an ``asyncio`` task alongside the uvicorn server.
    The SSE stream in ``main.py`` polls the state dict every second, so events
    appear on the frontend as they're appended here.
    """
    start_epoch = time.time()
    state["session_start_epoch"] = start_epoch
    state["orb_state"] = "idle"

    transcript_idx = 0
    finding_idx = 0
    decision_idx = 0

    logger.info("Demo scenario started — %d events queued", len(_build_script()))

    for delay, event_type, data in _build_script():
        await asyncio.sleep(delay)
        now = time.time()

        if event_type == "speaker":
            state.setdefault("speakers_list", [])
            if not any(s["id"] == data["id"] for s in state["speakers_list"]):
                state["speakers_list"].append(data)

        elif event_type == "orb":
            state["orb_state"] = data["state"]

        elif event_type == "transcript":
            state.setdefault("transcript_structured", [])
            state["transcript_structured"].append({
                **data,
                "timestamp": "",
                "epoch": now,
            })
            transcript_idx += 1

        elif event_type == "finding":
            state.setdefault("findings_structured", [])
            state["findings_structured"].append({**data, "epoch": now})
            finding_idx += 1

        elif event_type == "decision":
            state.setdefault("decisions_structured", [])
            state["decisions_structured"].append({**data, "epoch": now})
            decision_idx += 1

        elif event_type == "graph_trace":
            state.setdefault("graph_traces", [])
            state["graph_traces"].append({**data, "epoch": now})

        elif event_type == "timeline":
            state.setdefault("timeline", [])
            state["timeline"].append({**data, "epoch": now})

    logger.info(
        "Demo scenario complete — %d transcript, %d findings, %d decisions",
        transcript_idx,
        finding_idx,
        decision_idx,
    )
