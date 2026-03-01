"""Service graph tools — dependency graph, health status, and service metadata."""

from __future__ import annotations

import json
import logging

from livekit.agents import function_tool

from ..config import MOCK_DATA_DIR
from ._util import truncate

logger = logging.getLogger(__name__)


def _load_graph() -> dict:
    path = MOCK_DATA_DIR / "service_graph.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"services": {}, "dependency_graph": {}, "incident_impact": {}}


@function_tool()
async def get_service_graph() -> str:
    """Return the full service dependency graph and health status for all services.

    Shows which services depend on which, plus current health for each.
    """
    graph = _load_graph()
    services = graph.get("services", {})
    deps = graph.get("dependency_graph", {})
    impact = graph.get("incident_impact", {})

    lines = ["Service dependency graph and health:\n"]
    for name, svc in services.items():
        health = svc.get("health", "unknown").upper()
        reason = svc.get("health_reason", "")
        downstream = deps.get(name, [])
        infra = svc.get("infra", {})
        cloud = infra.get("cloud", "").upper() if infra else ""

        status_icon = {"HEALTHY": "✓", "DEGRADED": "~", "UNHEALTHY": "✗"}.get(health, "?")
        lines.append(f"{status_icon} {name} [{health}] ({cloud})")
        if reason:
            lines.append(f"    Reason: {reason}")
        if downstream:
            lines.append(f"    Depends on: {', '.join(downstream)}")
        lines.append("")

    if impact:
        lines.append("Incident impact summary:")
        lines.append(f"  Root causes: {', '.join(impact.get('root_causes', []))}")
        lines.append(f"  Unhealthy: {', '.join(impact.get('affected_services', []))}")
        lines.append(f"  Partially degraded: {', '.join(impact.get('partial_impact', []))}")
        lines.append(f"  Unaffected: {', '.join(impact.get('unaffected', []))}")

    return truncate("\n".join(lines))


@function_tool()
async def get_service_dependencies(service: str) -> str:
    """Get the dependencies of a specific service and their current health.

    Args:
        service: Service name, e.g. 'backboard-gateway' or 'livekit-agent'
    """
    graph = _load_graph()
    services = graph.get("services", {})
    deps = graph.get("dependency_graph", {})

    if service not in services and service not in deps:
        available = list(services.keys())
        return f"Service '{service}' not found. Available services: {', '.join(available)}"

    svc_deps = deps.get(service, [])
    svc_info = services.get(service, {})

    lines = [f"Service: {service}\n"]
    health = svc_info.get("health", "unknown").upper()
    reason = svc_info.get("health_reason", "")
    lines.append(f"Health: {health}")
    if reason:
        lines.append(f"Reason: {reason}")
    lines.append(f"Version: {svc_info.get('version', 'N/A')}")
    lines.append(f"Description: {svc_info.get('description', 'N/A')}")
    lines.append("")

    if svc_deps:
        lines.append(f"Direct dependencies ({len(svc_deps)}):")
        for dep in svc_deps:
            dep_info = services.get(dep, {})
            dep_health = dep_info.get("health", "unknown").upper()
            dep_reason = dep_info.get("health_reason", "")
            lines.append(f"  - {dep}: {dep_health}" + (f" — {dep_reason}" if dep_reason else ""))
    else:
        lines.append("No upstream dependencies.")

    # Find who depends on this service
    dependents = [svc for svc, svc_dep_list in deps.items() if service in svc_dep_list]
    if dependents:
        lines.append(f"\nDownstream services depending on {service}:")
        for d in dependents:
            d_health = services.get(d, {}).get("health", "unknown").upper()
            lines.append(f"  - {d}: {d_health}")

    return "\n".join(lines)


@function_tool()
async def get_service_health() -> str:
    """Get a quick health summary for all services — useful for triage.

    Returns a concise status list sorted by health (unhealthy first).
    """
    graph = _load_graph()
    services = graph.get("services", {})

    health_order = {"unhealthy": 0, "degraded": 1, "healthy": 2}
    sorted_services = sorted(
        services.items(),
        key=lambda x: health_order.get(x[1].get("health", "healthy"), 3),
    )

    lines = ["Service health summary:\n"]
    for name, svc in sorted_services:
        health = svc.get("health", "unknown").upper()
        reason = svc.get("health_reason") or "OK"
        infra = svc.get("infra", {})
        cloud = infra.get("cloud", "").upper() if infra else ""
        runtime = infra.get("runtime", "") if infra else ""

        lines.append(f"[{health:10s}] {name:30s} ({cloud}/{runtime})")
        if health != "HEALTHY":
            lines.append(f"             → {reason}")

    unhealthy = sum(1 for _, s in services.items() if s.get("health") == "unhealthy")
    degraded = sum(1 for _, s in services.items() if s.get("health") == "degraded")
    healthy = sum(1 for _, s in services.items() if s.get("health") == "healthy")
    lines.append(f"\nTotal: {healthy} healthy, {degraded} degraded, {unhealthy} unhealthy")

    return "\n".join(lines)
