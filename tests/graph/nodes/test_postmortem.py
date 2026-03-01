"""Tests for postmortem node — structured incident report generation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import war_room_copilot.graph.nodes.postmortem as pm_mod
from tests.conftest import make_incident_state
from war_room_copilot.graph.nodes.postmortem import postmortem_node

# ── postmortem_node ───────────────────────────────────────────────────────────


async def test_postmortem_no_context_early_return() -> None:
    """Empty state returns early without calling LLM."""
    result = await postmortem_node(make_incident_state())
    assert "Not enough incident data" in result["messages"][0].content


async def test_postmortem_generates_report(monkeypatch: object, tmp_path: Path) -> None:
    """Report is generated and saved to file."""
    monkeypatch.setattr(pm_mod, "POSTMORTEM_DIR", tmp_path / "postmortems")  # type: ignore[attr-defined]

    report_text = "INCIDENT SUMMARY: Server went down at 10:00."
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content=report_text)

    state = make_incident_state(
        transcript=["10:00 Alice: alert fired", "10:05 Bob: checking logs"],
        findings=["DB latency spike"],
        decisions=["Roll back checkout"],
    )

    with patch("war_room_copilot.graph.nodes.postmortem.get_graph_llm", return_value=mock_llm):
        result = await postmortem_node(state)

    assert "Post-mortem generated:" in result["findings"][0]
    assert "I have generated a post-mortem document" in result["messages"][0].content

    # Verify file was written
    postmortem_dir = tmp_path / "postmortems"
    files = list(postmortem_dir.glob("postmortem_*.txt"))
    assert len(files) == 1
    assert report_text in files[0].read_text()


async def test_postmortem_truncates_transcript(monkeypatch: object, tmp_path: Path) -> None:
    """Transcript > 100 lines is truncated with prefix showing omitted count."""
    monkeypatch.setattr(pm_mod, "POSTMORTEM_DIR", tmp_path / "postmortems")  # type: ignore[attr-defined]

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="report")

    lines = [f"line_{i}" for i in range(150)]
    state = make_incident_state(transcript=lines)

    with patch("war_room_copilot.graph.nodes.postmortem.get_graph_llm", return_value=mock_llm):
        await postmortem_node(state)

    content = mock_llm.ainvoke.call_args[0][0][1].content
    assert "50 earlier lines omitted" in content
    assert "line_50" in content  # first of the last 100
    assert "line_0" not in content


async def test_postmortem_llm_exception_fallback() -> None:
    """LLM failure returns fallback without writing a file."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = RuntimeError("LLM down")

    state = make_incident_state(transcript=["something happened"])

    with patch("war_room_copilot.graph.nodes.postmortem.get_graph_llm", return_value=mock_llm):
        result = await postmortem_node(state)

    assert "Unable to generate post-mortem" in result["messages"][0].content
    assert "findings" not in result


async def test_postmortem_summary_truncated(monkeypatch: object, tmp_path: Path) -> None:
    """Summary spoken aloud is truncated to first 500 chars of the report."""
    monkeypatch.setattr(pm_mod, "POSTMORTEM_DIR", tmp_path / "postmortems")  # type: ignore[attr-defined]

    long_report = "A" * 1000
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content=long_report)

    state = make_incident_state(transcript=["event happened"])

    with patch("war_room_copilot.graph.nodes.postmortem.get_graph_llm", return_value=mock_llm):
        result = await postmortem_node(state)

    summary = result["messages"][0].content
    # Summary includes prefix text + first 500 chars of report
    assert "A" * 500 in summary
    assert "A" * 501 not in summary.split("overview. ")[1]
