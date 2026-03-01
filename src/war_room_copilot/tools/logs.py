"""Multi-cloud log tools — AWS CloudWatch/ECS/Lambda, GCP Cloud Logging/GKE, Azure Monitor/AKS.

All functions return mock data from mock_data/*.json fixtures.
Each is marked with a TODO for replacement with a real SDK call.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

_MOCK_DATA_DIR = Path(__file__).parent.parent.parent.parent / "mock_data"


def _load_mock(filename: str) -> dict:
    path = _MOCK_DATA_DIR / filename
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _truncate(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated at {limit} chars]"


# ---------------------------------------------------------------------------
# AWS — CloudWatch
# ---------------------------------------------------------------------------


@function_tool()
async def query_cloudwatch_logs(log_group: str, query: str = "", minutes_ago: int = 30) -> str:
    """Query AWS CloudWatch Logs Insights for a log group.

    Args:
        log_group: CloudWatch log group name, e.g. '/ecs/war-room-prod/livekit-agent'
            or '/aws/rds/war-room-db/postgresql'
        query: Optional text filter to search within log events
        minutes_ago: How far back to search (default: last 30 minutes)
    """
    # TODO: replace with real SDK call:
    # import boto3
    # client = boto3.client("logs")
    # result = client.start_query(
    #     logGroupName=log_group,
    #     startTime=int((datetime.now() - timedelta(minutes=minutes_ago)).timestamp()),
    #     endTime=int(datetime.now().timestamp()),
    #     queryString=(
    #         f"fields @timestamp, @message | filter @message like '{query}'"
    #         " | sort @timestamp desc | limit 50"
    #     )
    # )
    # ... poll for results ...

    mock = _load_mock("aws_logs.json")
    groups = mock.get("cloudwatch_log_groups", {})
    group_data = groups.get(log_group)

    if not group_data:
        # Try partial match
        for key in groups:
            if log_group in key or key in log_group:
                group_data = groups[key]
                log_group = key
                break

    if not group_data:
        available = list(groups.keys())
        return (
            f"[Mock] No CloudWatch log group found matching '{log_group}'.\n"
            f"Available mock log groups: {', '.join(available)}"
        )

    events = group_data.get("events", [])
    if query:
        events = [e for e in events if query.lower() in e.get("message", "").lower()]

    if not events:
        return (
            f"[Mock] No log events in '{log_group}' matching '{query}' "
            f"in the last {minutes_ago} minutes."
        )

    lines = [f"[Mock] CloudWatch Logs — {log_group} (last {minutes_ago} min, filter: '{query}'):\n"]
    for e in events:
        lines.append(f"{e.get('timestamp', '')}  {e.get('message', '')}")

    return _truncate("\n".join(lines))


@function_tool()
async def query_ecs_logs(cluster: str, service: str, minutes_ago: int = 30) -> str:
    """Query AWS ECS task logs and service health for a given cluster and service.

    Args:
        cluster: ECS cluster name, e.g. 'war-room-prod'
        service: ECS service name, e.g. 'backboard-gateway-svc' or 'livekit-agent-svc'
        minutes_ago: How far back to look (default: last 30 minutes)
    """
    # TODO: replace with real SDK call:
    # import boto3
    # ecs = boto3.client("ecs")
    # tasks = ecs.list_tasks(cluster=cluster, serviceName=service)
    # logs = boto3.client("logs")
    # ... fetch task logs from CloudWatch ...

    mock = _load_mock("aws_logs.json")
    metrics = mock.get("ecs_metrics", {})
    services = metrics.get("services", {})

    svc_data = services.get(service)
    if not svc_data:
        for key in services:
            if service in key or key in service:
                svc_data = services[key]
                service = key
                break

    if not svc_data:
        return (
            f"[Mock] No ECS service found matching '{service}' in cluster '{cluster}'.\n"
            f"Available mock services: {', '.join(services.keys())}"
        )

    status = "HEALTHY" if svc_data["running_count"] == svc_data["desired_count"] else "DEGRADED"
    return (
        f"[Mock] ECS Service: {service} in cluster {cluster}\n"
        f"  Status: {status}\n"
        f"  Running: {svc_data['running_count']}/{svc_data['desired_count']} tasks\n"
        f"  Pending: {svc_data['pending_count']}\n"
        f"  CPU Utilization: {svc_data['cpu_utilization_pct']}%\n"
        f"  Memory Utilization: {svc_data['memory_utilization_pct']}%\n"
        f"  Task Definition: {svc_data['task_definition']}\n"
        f"  Time window: last {minutes_ago} minutes"
    )


@function_tool()
async def query_lambda_logs(function_name: str, minutes_ago: int = 30) -> str:
    """Query AWS Lambda function logs from CloudWatch.

    Args:
        function_name: Lambda function name, e.g. 'war-room-webhook-handler'
        minutes_ago: How far back to look (default: last 30 minutes)
    """
    # TODO: replace with real SDK call:
    # import boto3
    # logs = boto3.client("logs")
    # log_group = f"/aws/lambda/{function_name}"
    # ... query CloudWatch Logs Insights ...

    log_group = f"/aws/lambda/{function_name}"
    return await query_cloudwatch_logs(log_group=log_group, minutes_ago=minutes_ago)


# ---------------------------------------------------------------------------
# GCP — Cloud Logging / GKE
# ---------------------------------------------------------------------------


@function_tool()
async def query_gcp_logs(
    project: str,
    resource_type: str = "k8s_container",
    severity: str = "ERROR",
    minutes_ago: int = 30,
) -> str:
    """Query GCP Cloud Logging for log entries by resource type and severity.

    Args:
        project: GCP project ID, e.g. 'war-room-prod'
        resource_type: Resource type filter, e.g. 'k8s_container', 'cloud_run_revision'
        severity: Minimum severity: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
        minutes_ago: How far back to search (default: last 30 minutes)
    """
    # TODO: replace with real SDK call:
    # from google.cloud import logging as gcp_logging
    # client = gcp_logging.Client(project=project)
    # filter_str = (
    #     f'resource.type="{resource_type}" severity>={severity} '
    #     f'timestamp>="..."'
    # )
    # entries = list(client.list_entries(filter_=filter_str, max_results=50))

    mock = _load_mock("gcp_logs.json")
    all_logs = []

    severity_order = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
    min_level = severity_order.get(severity.upper(), 3)

    namespaces = mock.get("gke_logs", {}).get("namespaces", {})
    for ns_name, ns_data in namespaces.items():
        for pod in ns_data.get("pods", []):
            for log in pod.get("logs", []):
                log_level = severity_order.get(log.get("severity", "INFO"), 1)
                if log_level >= min_level:
                    all_logs.append(
                        {
                            "timestamp": log.get("timestamp", ""),
                            "severity": log.get("severity", ""),
                            "pod": pod.get("name", ""),
                            "namespace": ns_name,
                            "message": log.get("message", ""),
                        }
                    )

    if not all_logs:
        return (
            f"[Mock] No GCP logs in project '{project}' "
            f"for resource_type='{resource_type}' severity>={severity}."
        )

    all_logs.sort(key=lambda x: x["timestamp"], reverse=True)
    header = (
        f"[Mock] GCP Cloud Logging — project: {project} | "
        f"resource: {resource_type} | severity>={severity} | last {minutes_ago}min:\n"
    )
    lines = [header]
    for log in all_logs[:20]:
        sev = log["severity"]
        ns = log["namespace"]
        pod = log["pod"]
        msg = log["message"]
        lines.append(f"{log['timestamp']} [{sev}] {ns}/{pod}: {msg}")

    return _truncate("\n".join(lines))


@function_tool()
async def query_gke_pod_logs(
    cluster: str, namespace: str, pod_prefix: str = "", minutes_ago: int = 30
) -> str:
    """Query GKE pod logs and pod status for a namespace.

    Args:
        cluster: GKE cluster name, e.g. 'war-room-gke-prod'
        namespace: Kubernetes namespace, e.g. 'stt' or 'archiver'
        pod_prefix: Optional pod name prefix to filter, e.g. 'speechmatics-proxy'
        minutes_ago: How far back to look (default: last 30 minutes)
    """
    # TODO: replace with real SDK call:
    # from kubernetes import client as k8s_client, config as k8s_config
    # k8s_config.load_incluster_config()  # or load_kube_config() locally
    # v1 = k8s_client.CoreV1Api()
    # pods = v1.list_namespaced_pod(namespace, label_selector=f"app={pod_prefix}")
    # for pod in pods.items:
    #     logs = v1.read_namespaced_pod_log(
    #         name=pod.metadata.name, namespace=namespace, tail_lines=100
    #     )

    mock = _load_mock("gcp_logs.json")
    namespaces = mock.get("gke_logs", {}).get("namespaces", {})
    ns_data = namespaces.get(namespace)

    if not ns_data:
        available = list(namespaces.keys())
        return (
            f"[Mock] No GKE namespace '{namespace}' found in cluster '{cluster}'.\n"
            f"Available mock namespaces: {', '.join(available)}"
        )

    pods = ns_data.get("pods", [])
    if pod_prefix:
        pods = [p for p in pods if pod_prefix in p.get("name", "")]

    if not pods:
        return f"[Mock] No pods found matching prefix '{pod_prefix}' in namespace '{namespace}'."

    lines = [f"[Mock] GKE cluster={cluster} namespace={namespace} (last {minutes_ago} min):\n"]
    for pod in pods:
        status = pod.get("status", "Unknown")
        restarts = pod.get("restarts", 0)
        last_restart = pod.get("last_restart", "N/A")
        lines.append(
            f"Pod: {pod['name']}\n"
            f"  Status: {status} | Restarts: {restarts}"
            + (f" | Last restart: {last_restart}" if restarts > 0 else "")
        )
        container = pod.get("container", {})
        if container.get("last_state"):
            terminated = container["last_state"].get("terminated", {})
            lines.append(
                f"  Last termination: exitCode={terminated.get('exitCode')} "
                f"reason={terminated.get('reason')} at {terminated.get('finishedAt')}"
            )
        for log in pod.get("logs", []):
            ts = log.get("timestamp", "")
            sev = log.get("severity", "")
            msg = log.get("message", "")
            lines.append(f"  {ts} [{sev}] {msg}")
        lines.append("")

    return _truncate("\n".join(lines))


# ---------------------------------------------------------------------------
# Azure — Monitor / AKS
# ---------------------------------------------------------------------------


@function_tool()
async def query_azure_monitor(workspace_id: str, query: str, minutes_ago: int = 30) -> str:
    """Query Azure Monitor Log Analytics workspace using KQL.

    Args:
        workspace_id: Log Analytics workspace ID (GUID or name), e.g. 'war-room-workspace'
        query: KQL query string, e.g. 'AzureDiagnostics | where Category == "kube-audit"'
        minutes_ago: Time window — used to inject 'ago(Xm)' into query if not specified
    """
    # TODO: replace with real SDK call:
    # from azure.monitor.query import LogsQueryClient
    # from azure.identity import DefaultAzureCredential
    # from datetime import timedelta
    # credential = DefaultAzureCredential()
    # client = LogsQueryClient(credential)
    # response = client.query_workspace(
    #     workspace_id=workspace_id,
    #     query=query,
    #     timespan=timedelta(minutes=minutes_ago)
    # )

    mock = _load_mock("azure_logs.json")
    # Return Application Insights telemetry as mock Azure Monitor data
    telemetry = mock.get("application_insights", {}).get("telemetry", [])
    kql_example = mock.get("azure_monitor_queries", {}).get("example_kql", "")

    if not telemetry:
        return f"[Mock] No Azure Monitor data found for workspace '{workspace_id}'."

    lines = [
        f"[Mock] Azure Monitor Log Analytics — workspace: {workspace_id} "
        f"| last {minutes_ago} min:\n"
    ]
    lines.append(f"Query: {query}\n")
    lines.append(
        f"Example KQL for OOMKilled events:\n  {kql_example}\n\n"
        "Results (Application Insights telemetry):\n"
    )

    for entry in telemetry:
        ts = entry.get("timestamp", "")
        etype = entry.get("type", "")
        name = entry.get("name", entry.get("exception", ""))
        duration = entry.get("duration_ms", "")
        success = entry.get("success", True)
        resp_code = entry.get("response_code", "")
        msg = entry.get("message", "")
        count = entry.get("count", 1)

        detail = f"{ts} [{etype.upper()}] {name}"
        if duration:
            detail += f" ({duration}ms)"
        if resp_code:
            detail += f" HTTP {resp_code}"
        if not success:
            detail += " FAILED"
        if msg:
            detail += f"\n    {msg}"
        if count > 1:
            detail += f" (x{count})"
        lines.append(detail)

    return _truncate("\n".join(lines))


@function_tool()
async def query_aks_logs(cluster: str, namespace: str, minutes_ago: int = 30) -> str:
    """Query Azure AKS pod logs and deployment status for a namespace.

    Args:
        cluster: AKS cluster name, e.g. 'war-room-aks-prod'
        namespace: Kubernetes namespace, e.g. 'tts' or 'agent-backup'
        minutes_ago: How far back to look (default: last 30 minutes)
    """
    # TODO: replace with real SDK call:
    # from azure.mgmt.containerservice import ContainerServiceClient
    # from azure.identity import DefaultAzureCredential
    # credential = DefaultAzureCredential()
    # aks_client = ContainerServiceClient(credential, subscription_id)
    # ... or use kubectl via kubeconfig for log streaming

    mock = _load_mock("azure_logs.json")
    aks_data = mock.get("aks_logs", {})
    namespaces = aks_data.get("namespaces", {})

    ns_data = namespaces.get(namespace)
    if not ns_data:
        available = list(namespaces.keys())
        return (
            f"[Mock] No AKS namespace '{namespace}' found in cluster '{cluster}'.\n"
            f"Available mock namespaces: {', '.join(available)}"
        )

    pods = ns_data.get("pods", [])
    deployments = ns_data.get("deployments", [])

    lines = [f"[Mock] AKS cluster={cluster} namespace={namespace} (last {minutes_ago} min):\n"]

    if deployments:
        lines.append("Deployments:")
        for d in deployments:
            ready = d.get("ready_replicas", 0)
            desired = d.get("desired_replicas", 0)
            status = "HEALTHY" if ready == desired else "DEGRADED"
            lines.append(
                f"  {d['name']}: {ready}/{desired} replicas [{status}] "
                f"| image: {d.get('image', 'N/A')} "
                f"| deployed: {d.get('last_deployed', 'N/A')}"
            )
        lines.append("")

    if pods:
        lines.append("Pods:")
        for pod in pods:
            status = pod.get("status", "Unknown")
            restarts = pod.get("restarts", 0)
            lines.append(f"  {pod['name']}: {status} | Restarts: {restarts}")
            container = pod.get("container", {})
            mem = f"{container.get('memory_request', '?')}/{container.get('memory_limit', '?')}"
            lines.append(f"    Image: {container.get('image', 'N/A')} | Memory: {mem}")
            for log in pod.get("logs", []):
                sev = log.get("severity", "INFO")
                lines.append(f"    {log.get('timestamp', '')} [{sev}] {log.get('message', '')}")
            lines.append("")

    return _truncate("\n".join(lines))
