"""Tests for tools._registry — schema generation and tool discovery."""

from __future__ import annotations

from src.war_room_copilot.tools import ALL_TOOLS
from src.war_room_copilot.tools._registry import get_openai_schemas, tool_to_openai_schema


class TestAllToolsDiscovered:
    def test_count(self) -> None:
        # 10 github + 4 datadog + 7 cloud logs + 3 service graph + 1 runbook + 1 recall = 26
        assert len(ALL_TOOLS) == 26, f"Expected 26 tools, got {len(ALL_TOOLS)}: {sorted(ALL_TOOLS)}"

    def test_known_tools_present(self) -> None:
        expected = {
            "search_code",
            "get_recent_commits",
            "get_commit_diff",
            "list_pull_requests",
            "search_issues",
            "read_file",
            "get_blame",
            "create_github_issue",
            "revert_commit",
            "close_pull_request",
            "query_datadog_metrics",
            "query_datadog_logs",
            "query_datadog_apm",
            "get_datadog_monitors",
            "query_cloudwatch_logs",
            "query_ecs_logs",
            "query_lambda_logs",
            "query_gcp_logs",
            "query_gke_pod_logs",
            "query_azure_monitor",
            "query_aks_logs",
            "get_service_graph",
            "get_service_dependencies",
            "get_service_health",
            "search_runbook",
            "recall_decision",
        }
        assert set(ALL_TOOLS.keys()) == expected


class TestSchemaStructure:
    def test_each_schema_has_required_fields(self) -> None:
        schemas = get_openai_schemas(ALL_TOOLS)
        assert len(schemas) == len(ALL_TOOLS)
        for schema in schemas:
            assert schema["type"] == "function"
            fn = schema["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn
            params = fn["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params

    def test_required_params_correct(self) -> None:
        schemas = get_openai_schemas(ALL_TOOLS)
        schema_map = {s["function"]["name"]: s for s in schemas}

        # search_code requires 'query'
        sc = schema_map["search_code"]
        assert "query" in sc["function"]["parameters"]["required"]
        # repo is optional
        assert "repo" not in sc["function"]["parameters"]["required"]

        # get_datadog_monitors has no required params
        gm = schema_map["get_datadog_monitors"]
        assert gm["function"]["parameters"]["required"] == []

        # query_datadog_apm requires 'service'
        apm = schema_map["query_datadog_apm"]
        assert "service" in apm["function"]["parameters"]["required"]


class TestSingleToolSchema:
    def test_tool_to_openai_schema(self) -> None:
        tool = ALL_TOOLS["search_code"]
        schema = tool_to_openai_schema(tool)
        assert schema["function"]["name"] == "search_code"
        assert "query" in schema["function"]["parameters"]["properties"]
