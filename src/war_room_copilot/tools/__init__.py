"""Tool registry — exposes ALL_TOOLS for agent and investigation runner."""

from __future__ import annotations

from typing import Any

from .datadog import (
    get_datadog_monitors,
    query_datadog_apm,
    query_datadog_logs,
    query_datadog_metrics,
)
from .github import (
    close_pull_request,
    create_github_issue,
    get_blame,
    get_commit_diff,
    get_recent_commits,
    list_pull_requests,
    read_file,
    revert_commit,
    search_code,
    search_issues,
)
from .logs import (
    query_aks_logs,
    query_azure_monitor,
    query_cloudwatch_logs,
    query_ecs_logs,
    query_gcp_logs,
    query_gke_pod_logs,
    query_lambda_logs,
)
from .recall import recall_decision
from .runbook import search_runbook
from .service_graph import get_service_dependencies, get_service_graph, get_service_health

# Canonical map of every tool available to the agent.
# Keyed by the tool's registered name (which matches the function name).
ALL_TOOLS: dict[str, Any] = {
    t.info.name: t  # type: ignore[attr-defined]
    for t in [
        # GitHub — read
        search_code,
        get_recent_commits,
        get_commit_diff,
        list_pull_requests,
        search_issues,
        read_file,
        get_blame,
        # GitHub — write
        create_github_issue,
        revert_commit,
        close_pull_request,
        # Datadog
        query_datadog_metrics,
        query_datadog_logs,
        query_datadog_apm,
        get_datadog_monitors,
        # Cloud logs
        query_cloudwatch_logs,
        query_ecs_logs,
        query_lambda_logs,
        query_gcp_logs,
        query_gke_pod_logs,
        query_azure_monitor,
        query_aks_logs,
        # Service graph
        get_service_graph,
        get_service_dependencies,
        get_service_health,
        # Runbooks
        search_runbook,
        # Memory
        recall_decision,
    ]
}
