"""Runbook tool — search incident runbooks from mock_data/runbooks.yaml."""

from __future__ import annotations

import logging

import yaml
from livekit.agents import function_tool

from ..config import RUNBOOKS_FILE

logger = logging.getLogger(__name__)

_runbooks_cache: list[dict] | None = None


def _load_runbooks() -> list[dict]:
    global _runbooks_cache
    if _runbooks_cache is not None:
        return _runbooks_cache
    if not RUNBOOKS_FILE.exists():
        logger.warning(
            "runbooks.yaml not found at %s (resolved: %s)",
            RUNBOOKS_FILE,
            RUNBOOKS_FILE.resolve(),
        )
        return []
    with RUNBOOKS_FILE.open() as f:
        data = yaml.safe_load(f)
    # runbooks.yaml is a list at the top level, not a dict
    if isinstance(data, list):
        _runbooks_cache = data
    elif isinstance(data, dict):
        _runbooks_cache = data.get("runbooks", [])
    else:
        _runbooks_cache = []
    logger.info("Loaded %d runbooks from %s", len(_runbooks_cache), RUNBOOKS_FILE)
    return _runbooks_cache


@function_tool()
async def search_runbook(keywords: str) -> str:
    """Search incident runbooks by keyword.

    Matches against runbook title, description, and keyword tags.
    Returns matching runbooks with their step-by-step remediation instructions.

    Args:
        keywords: Space or comma-separated keywords to search, e.g. 'connection pool postgres'
                  or 'OOM crashloop pod' or 'rollback deploy'
    """
    runbooks = _load_runbooks()
    if not runbooks:
        return "No runbooks available — runbooks.yaml not found or empty."

    # Tokenize keywords
    tokens = [t.strip().lower() for t in keywords.replace(",", " ").split() if t.strip()]
    if not tokens:
        return "Please provide at least one keyword to search runbooks."

    scored: list[tuple[int, dict]] = []
    for rb in runbooks:
        score = 0
        searchable = " ".join(
            [
                rb.get("title", ""),
                rb.get("description", ""),
                " ".join(rb.get("keywords", [])),
            ]
        ).lower()

        for token in tokens:
            if token in searchable:
                score += 1
            # Boost for keyword list exact match
            if token in [k.lower() for k in rb.get("keywords", [])]:
                score += 1

        if score > 0:
            scored.append((score, rb))

    if not scored:
        all_keywords = []
        for rb in runbooks:
            all_keywords.extend(rb.get("keywords", []))
        return (
            f"No runbooks found matching: '{keywords}'.\n"
            f"Available runbook keywords: {', '.join(sorted(set(all_keywords)))}"
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:3]  # Return up to 3 best matches

    lines = [f"Found {len(scored)} matching runbook(s) for '{keywords}':\n"]
    for i, (score, rb) in enumerate(top, 1):
        lines.append(f"{'─' * 50}")
        lines.append(f"#{i}: {rb.get('title', 'Untitled')} (match score: {score})")
        if rb.get("description"):
            lines.append(f"Description: {rb['description']}")
        if rb.get("keywords"):
            lines.append(f"Tags: {', '.join(rb['keywords'])}")
        lines.append("\nSteps:")
        for j, step in enumerate(rb.get("steps", []), 1):
            lines.append(f"  {j}. {step}")
        lines.append("")

    return "\n".join(lines)
