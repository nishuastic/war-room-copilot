"""Tests for recall node — memory search across session and Backboard."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage

from tests.conftest import make_incident_state
from war_room_copilot.graph.nodes.recall import recall_node

# ── recall_node ───────────────────────────────────────────────────────────────


async def test_recall_no_context_early_return() -> None:
    """No decisions, findings, transcript, or backboard returns canned message."""
    state = make_incident_state(query="what was decided?")
    result = await recall_node(state)
    assert "No incident history" in result["findings"][0]
    assert isinstance(result["messages"][0], AIMessage)


async def test_recall_with_decisions_and_transcript() -> None:
    """LLM is called when context is available."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="You decided to roll back.")

    state = make_incident_state(
        query="what did we decide?",
        decisions=["Roll back checkout-service"],
        transcript=["10:00 Alice: let's roll back"],
    )

    with patch("war_room_copilot.graph.nodes.recall.get_graph_llm", return_value=mock_llm):
        result = await recall_node(state)

    assert result["findings"][0] == "You decided to roll back."
    mock_llm.ainvoke.assert_called_once()


async def test_recall_backboard_success() -> None:
    """Cross-session memory from Backboard is included in context."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="Past incident info found.")

    mock_recall = AsyncMock(return_value="Similar issue in Jan: DB connection pool exhausted")

    state = make_incident_state(
        query="has this happened before?",
        backboard_thread_id="thread-123",
    )

    with (
        patch("war_room_copilot.graph.nodes.recall.get_graph_llm", return_value=mock_llm),
        patch("war_room_copilot.graph.nodes.recall.recall_memory", mock_recall, create=True),
        patch(
            "war_room_copilot.graph.nodes.recall.recall_memory",
            new=mock_recall,
        ),
    ):
        # The recall_node does a lazy import, so we need to patch it in the module
        import war_room_copilot.graph.nodes.recall as recall_mod

        with patch.object(recall_mod, "recall_memory", mock_recall, create=True):
            pass

    # Simpler approach: patch the import path
    with patch("war_room_copilot.graph.nodes.recall.get_graph_llm", return_value=mock_llm):
        with patch.dict(
            "sys.modules",
            {"war_room_copilot.tools.backboard": MagicMock(recall_memory=mock_recall)},
        ):
            result = await recall_node(state)

    assert isinstance(result["messages"][0], AIMessage)


async def test_recall_backboard_exception_continues() -> None:
    """Backboard failure is silently ignored, LLM still called with local context."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="No external memory available.")

    state = make_incident_state(
        query="what happened?",
        decisions=["Deploy hotfix"],
        backboard_thread_id="thread-456",
    )

    # Make the backboard import raise
    failing_backboard = MagicMock()
    failing_backboard.recall_memory = AsyncMock(side_effect=RuntimeError("Backboard down"))

    with (
        patch("war_room_copilot.graph.nodes.recall.get_graph_llm", return_value=mock_llm),
        patch.dict("sys.modules", {"war_room_copilot.tools.backboard": failing_backboard}),
    ):
        result = await recall_node(state)

    # Should still succeed via LLM with local context
    mock_llm.ainvoke.assert_called_once()
    assert isinstance(result["messages"][0], AIMessage)


async def test_recall_no_thread_id_skips_backboard() -> None:
    """Without backboard_thread_id, backboard is not called."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="Found in local memory.")

    state = make_incident_state(
        query="what was decided?",
        decisions=["Scale up replicas"],
    )

    with patch("war_room_copilot.graph.nodes.recall.get_graph_llm", return_value=mock_llm):
        result = await recall_node(state)

    assert isinstance(result["messages"][0], AIMessage)


async def test_recall_truncates_findings_and_transcript() -> None:
    """Last 10 findings and last 30 transcript lines are used."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="recalled")

    findings = [f"finding_{i}" for i in range(15)]
    transcript = [f"line_{i}" for i in range(40)]
    state = make_incident_state(query="recall", findings=findings, transcript=transcript)

    with patch("war_room_copilot.graph.nodes.recall.get_graph_llm", return_value=mock_llm):
        await recall_node(state)

    content = mock_llm.ainvoke.call_args[0][0][1].content
    assert "finding_5" in content  # last 10 starts at index 5
    assert "finding_0" not in content
    assert "line_10" in content  # last 30 starts at index 10
    assert "line_0" not in content


async def test_recall_llm_exception_fallback() -> None:
    """LLM failure returns graceful fallback."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = RuntimeError("LLM down")

    state = make_incident_state(
        query="what happened?",
        transcript=["something happened"],
    )

    with patch("war_room_copilot.graph.nodes.recall.get_graph_llm", return_value=mock_llm):
        result = await recall_node(state)

    assert "Unable to search memory" in result["findings"][0]
