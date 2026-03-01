"""Pre-seed session state for live hackathon demo.

When ``DEMO_MODE=1`` is set, the agent boots with a "warm" session that
already has transcript history, findings, decisions, graph traces, and
timeline events — as if an incident has been underway for ~5 minutes.

The agent is LIVE (STT, LLM, TTS all work).  The seed data gives it
rich context so the LangGraph reasoning loop returns impressive answers
and the dashboard looks active from the first second.

Usage:  Set ``DEMO_MODE=1`` in ``.env`` or environment, then ``make up``.
"""

from __future__ import annotations

import time
from typing import Any


def seed_demo_state(state: dict[str, Any]) -> None:
    """Populate *state* in-place with realistic incident context.

    Call this right after ``_session_state`` is initialised in
    ``_entrypoint_inner()`` — before the dashboard API starts so the
    first ``/state`` response already contains data.
    """
    now = time.time()
    start = now - 300  # pretend session started 5 minutes ago
    state["session_start_epoch"] = start

    # ── Speakers ────────────────────────────────────────────────────
    state["speakers_list"] = [
        {"id": 1, "name": "Sarah Chen", "role": "Incident Commander", "colorVar": "--speaker-1"},
        {"id": 2, "name": "Marcus Johnson", "role": "SRE", "colorVar": "--speaker-2"},
        {"id": 3, "name": "Priya Patel", "role": "Backend Engineer", "colorVar": "--speaker-3"},
        {"id": 4, "name": "Alex Kim", "role": "DBA", "colorVar": "--speaker-4"},
    ]
    state["speakers"] = {s["name"]: s["name"] for s in state["speakers_list"]}

    # ── Transcript history (what "happened" before you joined) ──────
    transcript_lines = [
        (start + 10, "Sarah Chen",
         "Alright everyone, this is a SEV-1. Checkout service is returning 503s "
         "across all regions. Customer impact confirmed — about 15% of transactions failing."),
        (start + 25, "Marcus Johnson",
         "I'm seeing connection pool exhaustion on the primary DB cluster. "
         "Active connections spiked from 200 to 2,000 about 20 minutes ago."),
        (start + 45, "Priya Patel",
         "We deployed checkout-service v2.14.3 about an hour ago. "
         "Could be related to the new query optimization PR."),
        (start + 70, "War Room Copilot",
         "I found that PR #892 removed a compound index on the orders table. "
         "Without that index, checkout queries are doing sequential scans, "
         "which explains the connection pool exhaustion."),
        (start + 100, "Alex Kim",
         "That makes sense. Without the compound index, each checkout query "
         "holds a connection 10x longer. Pool fills up, new requests get 503s."),
        (start + 120, "Marcus Johnson",
         "p99 latency at 12 seconds, normally under 200ms. Error rate 15% and climbing."),
        (start + 150, "Priya Patel",
         "Wait, I think the deploy was actually 3 hours ago, not 1 hour."),
        (start + 170, "War Room Copilot",
         "Contradiction detected: Priya initially said the deploy was about an hour ago "
         "but now says 3 hours. GitHub deploy log shows v2.14.3 deployed at 14:32 UTC — "
         "that's 2 hours 47 minutes ago."),
        (start + 200, "War Room Copilot",
         "Found the trigger: the nightly-order-reconciliation cron job started 22 minutes ago. "
         "It generates 500+ concurrent checkout queries. Without the compound index, "
         "the cron job pushed the pool past its limit."),
        (start + 230, "Sarah Chen",
         "Here's the plan: kill the cron job, push emergency index migration, "
         "and bump the connection pool from 2,000 to 3,000."),
    ]

    for epoch, speaker, text in transcript_lines:
        state["transcript_structured"].append({
            "speaker": speaker,
            "text": text,
            "timestamp": "",
            "epoch": epoch,
        })
        # Legacy transcript format (used by LangGraph reasoning loop)
        ts = time.strftime("%H:%M:%S", time.gmtime(epoch))
        state["transcript"].append(f"[{ts}] {speaker}: {text}")

    # ── Findings ────────────────────────────────────────────────────
    state["findings_structured"] = [
        {
            "text": "PR #892 merged 2 hours ago: removes compound index on "
                    "orders(user_id, created_at), replaces with sequential scans",
            "source": "github",
            "epoch": start + 65,
        },
        {
            "text": "Issue #1247 (open): 'Connection pool exhaustion under load' — "
                    "reported 3 weeks ago with suggested fix",
            "source": "github",
            "epoch": start + 68,
        },
        {
            "text": "Metrics: p99 latency 12s (baseline 200ms), error rate 15%, "
                    "DB active connections 2,000/2,000 (pool saturated)",
            "source": "metrics",
            "epoch": start + 125,
        },
        {
            "text": "Cron job 'nightly-order-reconciliation' generates 500+ concurrent "
                    "checkout queries — triggered pool exhaustion",
            "source": "code",
            "epoch": start + 195,
        },
    ]
    # Also populate the flat findings list (used by LangGraph)
    state["findings"] = [f["text"] for f in state["findings_structured"]]

    # ── Decisions ───────────────────────────────────────────────────
    state["decisions_structured"] = [
        {"text": "Kill nightly-order-reconciliation cron job immediately",
         "speaker": "Sarah Chen", "epoch": start + 235},
        {"text": "Push emergency index migration to restore compound index",
         "speaker": "Sarah Chen", "epoch": start + 237},
        {"text": "Bump DB connection pool from 2,000 to 3,000",
         "speaker": "Sarah Chen", "epoch": start + 239},
    ]
    state["decisions"] = [d["text"] for d in state["decisions_structured"]]

    # ── Graph traces (show agent skills already activated) ──────────
    state["graph_traces"] = [
        {"node": "skill_router", "query": "checkout 503 connection pool exhaustion",
         "duration": 0.3, "epoch": start + 55},
        {"node": "investigate", "query": "checkout-service v2.14.3 changes",
         "duration": 2.1, "epoch": start + 60},
        {"node": "github", "query": "search_code: connection pool config",
         "duration": 1.5, "epoch": start + 63},
        {"node": "skill_router", "query": "contradiction: deploy timing",
         "duration": 0.2, "epoch": start + 155},
        {"node": "contradict", "query": "deploy 1hr vs 3hr ago",
         "duration": 1.8, "epoch": start + 160},
        {"node": "skill_router", "query": "what triggered pool exhaustion",
         "duration": 0.2, "epoch": start + 180},
        {"node": "recall", "query": "cron jobs, batch processes",
         "duration": 1.4, "epoch": start + 185},
    ]

    # ── Timeline ────────────────────────────────────────────────────
    state["timeline"] = [
        {"type": "transcript", "description": "SEV-1 declared: checkout 503s",
         "epoch": start + 10},
        {"type": "tool_call", "description": "Agent: investigate skill selected",
         "epoch": start + 55},
        {"type": "finding", "description": "PR #892 removed compound index",
         "epoch": start + 65},
        {"type": "finding", "description": "Metrics: p99 12s, pool saturated",
         "epoch": start + 125},
        {"type": "contradiction", "description": "Deploy timing mismatch: 1hr vs 3hr",
         "epoch": start + 160},
        {"type": "finding", "description": "Cron job triggered pool exhaustion",
         "epoch": start + 195},
        {"type": "decision", "description": "Kill cron job immediately",
         "epoch": start + 235},
        {"type": "decision", "description": "Restore compound index",
         "epoch": start + 237},
        {"type": "decision", "description": "Bump pool to 3,000",
         "epoch": start + 239},
    ]

    state["orb_state"] = "listening"
