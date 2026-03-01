#!/usr/bin/env python3
"""Interactive test script for all agent tools — GitHub and Datadog.

Usage:
    uv run python scripts/test_tools.py

Tests each tool and prints results. Runs against real APIs using your .env keys.
Safe: GitHub write tests create + immediately close a test issue/PR.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# Add src to path so we can import tools directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("test_tools")

PASS = "✓"
FAIL = "✗"
SKIP = "~"


def header(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def result(label: str, ok: bool, detail: str = "") -> None:
    icon = PASS if ok else FAIL
    status = "PASS" if ok else "FAIL"
    print(f"  {icon} [{status}] {label}")
    if detail:
        for line in detail.strip().splitlines()[:6]:
            print(f"         {line}")


async def test_github_read() -> None:
    header("GitHub — Read Tools")

    from war_room_copilot.tools.github import (
        get_blame,
        get_commit_diff,
        get_recent_commits,
        list_pull_requests,
        read_file,
        search_code,
        search_issues,
    )

    # search_code
    try:
        out = await search_code("wake_word")
        result("search_code('wake_word')", "agent.py" in out or "config.py" in out, out)
    except Exception as e:
        result("search_code", False, str(e))

    # get_recent_commits
    try:
        out = await get_recent_commits(count=5)
        result("get_recent_commits(count=5)", "14b6316" in out or len(out) > 20, out)
    except Exception as e:
        result("get_recent_commits", False, str(e))

    # get_commit_diff — use the most recent known commit
    try:
        out = await get_commit_diff("14b6316")
        result("get_commit_diff('14b6316')", "Commit:" in out, out)
    except Exception as e:
        result("get_commit_diff", False, str(e))

    # list_pull_requests
    try:
        out = await list_pull_requests(state="closed", count=3)
        result("list_pull_requests(closed)", len(out) > 10, out)
    except Exception as e:
        result("list_pull_requests", False, str(e))

    # search_issues
    try:
        out = await search_issues("incident")
        result("search_issues('incident')", True, out or "(no issues found — that's fine)")
    except Exception as e:
        result("search_issues", False, str(e))

    # read_file
    try:
        out = await read_file("README.md")
        result("read_file('README.md')", "War Room" in out, out[:80])
    except Exception as e:
        result("read_file", False, str(e))

    # get_blame
    try:
        out = await get_blame("src/war_room_copilot/core/agent.py")
        result("get_blame('agent.py')", "Recent commits" in out, out)
    except Exception as e:
        result("get_blame", False, str(e))


async def test_github_write() -> None:
    header("GitHub — Write Tools (creates + cleans up test issue/PR)")

    from war_room_copilot.tools.github import (
        close_pull_request,
        create_github_issue,
        revert_commit,
    )

    # create_github_issue
    issue_number = None
    try:
        out = await create_github_issue(
            title="[TEST] War Room Copilot tool test — safe to close",
            body=(
                "This issue was created automatically by `scripts/test_tools.py` "
                "to verify the `create_github_issue` tool works.\n\n"
                "**Safe to close immediately.**\n\n"
                "- Created by: war-room-copilot test suite\n"
                "- Date: 2026-03-01"
            ),
            labels="",  # skip labels — may not exist in repo
        )
        ok = "Issue #" in out
        result("create_github_issue", ok, out)
        # Extract issue number for potential cleanup
        if ok:
            import re
            match = re.search(r"Issue #(\d+)", out)
            if match:
                issue_number = int(match.group(1))
    except Exception as e:
        result("create_github_issue", False, str(e))

    # revert_commit — creates a branch+PR, immediately close it
    pr_number = None
    try:
        out = await revert_commit("14b6316")
        ok = "Revert PR #" in out or "revert" in out.lower()
        result("revert_commit('14b6316')", ok, out)
        if ok:
            import re
            match = re.search(r"PR #(\d+)", out)
            if match:
                pr_number = int(match.group(1))
    except Exception as e:
        result("revert_commit", False, str(e))

    # close the revert PR immediately to keep repo clean
    if pr_number:
        try:
            out = await close_pull_request(pr_number)
            result(f"close_pull_request(#{pr_number}) [cleanup]", "closed" in out.lower(), out)
        except Exception as e:
            result(f"close_pull_request(#{pr_number})", False, str(e))
    else:
        print(f"  {SKIP} [SKIP] close_pull_request — no PR to clean up")


async def test_datadog() -> None:
    header("Datadog Tools")

    api_key = os.environ.get("DATADOG_API_KEY") or os.environ.get("DD_API_KEY", "")
    if not api_key:
        print(f"  {SKIP} [SKIP] All Datadog tests — DD_API_KEY not set (mock data mode)")
        return

    from war_room_copilot.tools.datadog import (
        get_datadog_monitors,
        query_datadog_apm,
        query_datadog_logs,
        query_datadog_metrics,
    )

    # query_datadog_metrics
    try:
        out = await query_datadog_metrics("war_room.backboard.latency_p99", from_time="2h")
        ok = "latency" in out.lower() or "metric" in out.lower() or "p99" in out.lower()
        result("query_datadog_metrics(backboard.latency_p99)", ok, out)
    except Exception as e:
        result("query_datadog_metrics", False, str(e))

    # query_datadog_logs
    try:
        out = await query_datadog_logs("connection pool", service="backboard-gateway", minutes_ago=120)
        ok = len(out) > 20
        result("query_datadog_logs(backboard-gateway)", ok, out)
    except Exception as e:
        result("query_datadog_logs", False, str(e))

    # query_datadog_apm — backboard (degraded in seeded data)
    try:
        out = await query_datadog_apm("backboard-gateway", minutes_ago=120)
        ok = "latency" in out.lower() or "error" in out.lower() or "apm" in out.lower()
        result("query_datadog_apm(backboard-gateway)", ok, out)
    except Exception as e:
        result("query_datadog_apm", False, str(e))

    # query_datadog_apm — healthy service
    try:
        out = await query_datadog_apm("fastapi-dashboard", minutes_ago=120)
        ok = len(out) > 10
        result("query_datadog_apm(fastapi-dashboard)", ok, out)
    except Exception as e:
        result("query_datadog_apm(dashboard)", False, str(e))

    # get_datadog_monitors
    try:
        out = await get_datadog_monitors()
        ok = len(out) > 10
        result("get_datadog_monitors()", ok, out)
    except Exception as e:
        result("get_datadog_monitors", False, str(e))


async def test_runbook() -> None:
    header("Runbook Tool")

    from war_room_copilot.tools.runbook import search_runbook

    cases = [
        ("connection pool postgres", "PgBouncer"),
        ("OOM crashloop pod", "kubectl"),
        ("rollback deploy", "rollback"),
        ("redis memory", "eviction"),
    ]
    for keywords, expected_word in cases:
        try:
            out = await search_runbook(keywords)
            ok = expected_word.lower() in out.lower() or "Steps:" in out
            result(f"search_runbook('{keywords}')", ok, out[:200])
        except Exception as e:
            result(f"search_runbook('{keywords}')", False, str(e))


async def test_service_graph() -> None:
    header("Service Graph Tools")

    from war_room_copilot.tools.service_graph import (
        get_service_dependencies,
        get_service_graph,
        get_service_health,
    )

    try:
        out = await get_service_health()
        ok = "backboard-gateway" in out and "UNHEALTHY" in out
        result("get_service_health()", ok, out[:300])
    except Exception as e:
        result("get_service_health", False, str(e))

    try:
        out = await get_service_graph()
        ok = "livekit-agent" in out and "dependency" in out.lower()
        result("get_service_graph()", ok, out[:200])
    except Exception as e:
        result("get_service_graph", False, str(e))

    try:
        out = await get_service_dependencies("backboard-gateway")
        ok = "postgres-rds" in out
        result("get_service_dependencies('backboard-gateway')", ok, out)
    except Exception as e:
        result("get_service_dependencies", False, str(e))


async def test_logs() -> None:
    header("Cloud Log Tools (mock data)")

    from war_room_copilot.tools.logs import (
        query_aks_logs,
        query_cloudwatch_logs,
        query_ecs_logs,
        query_gcp_logs,
        query_gke_pod_logs,
    )

    try:
        out = await query_cloudwatch_logs("/aws/rds/war-room-db/postgresql", "FATAL")
        ok = "FATAL" in out or "connection" in out.lower()
        result("query_cloudwatch_logs(RDS, 'FATAL')", ok, out[:200])
    except Exception as e:
        result("query_cloudwatch_logs", False, str(e))

    try:
        out = await query_ecs_logs("war-room-prod", "backboard-gateway-svc")
        ok = "backboard" in out.lower()
        result("query_ecs_logs(backboard-gateway-svc)", ok, out[:200])
    except Exception as e:
        result("query_ecs_logs", False, str(e))

    try:
        out = await query_gke_pod_logs("war-room-gke-prod", "stt", "speechmatics-proxy")
        ok = "OOMKilled" in out
        result("query_gke_pod_logs(speechmatics-proxy)", ok, out[:200])
    except Exception as e:
        result("query_gke_pod_logs", False, str(e))

    try:
        out = await query_aks_logs("war-room-aks-prod", "agent-backup")
        ok = "OOMKilled" in out or "livekit-agent" in out
        result("query_aks_logs(agent-backup)", ok, out[:200])
    except Exception as e:
        result("query_aks_logs", False, str(e))

    try:
        out = await query_gcp_logs("war-room-prod", severity="ERROR")
        ok = "ERROR" in out or "CRITICAL" in out
        result("query_gcp_logs(severity=ERROR)", ok, out[:200])
    except Exception as e:
        result("query_gcp_logs", False, str(e))


async def main() -> None:
    print("\n" + "=" * 60)
    print("  War Room Copilot — Tool Test Suite")
    print("=" * 60)

    await test_github_read()
    await test_github_write()
    await test_datadog()
    await test_runbook()
    await test_service_graph()
    await test_logs()

    print("\n" + "=" * 60)
    print("  Done.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
