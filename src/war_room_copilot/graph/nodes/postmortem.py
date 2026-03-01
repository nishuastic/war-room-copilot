"""Post-mortem node — generates a structured incident report."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from war_room_copilot.graph.llm import get_graph_llm
from war_room_copilot.graph.state import IncidentState

logger = logging.getLogger("war-room-copilot.graph.nodes.postmortem")

# Maximum transcript lines sent to the LLM to avoid context overflow
_MAX_TRANSCRIPT_LINES = 100

# Output directory for postmortem files — inside the persistent data volume
_DATA_DIR = Path(os.environ.get("APP_DATA_DIR", Path(__file__).parents[4] / "data"))
POSTMORTEM_DIR = _DATA_DIR / "postmortems"

POSTMORTEM_SYSTEM_PROMPT = SystemMessage(
    content="""\
You are generating a post-mortem draft from a production incident \
war room conversation.
Using the transcript, findings, and decisions provided, create a \
structured post-mortem with these sections:

INCIDENT SUMMARY: 2-3 sentence overview
IMPACT: What was affected, duration, severity
TIMELINE: Chronological events with timestamps and who reported them
ROOT CAUSE: What caused the incident (if determined)
CONTRIBUTING FACTORS: What made detection or resolution harder
ACTIONS TAKEN: What was done during the incident
ACTION ITEMS: Follow-up work needed (with suggested owners)

Keep each section concise. Use plain language. \
If information for a section is not available, say \
"To be determined" rather than guessing.
Do not use markdown formatting. Use plain text headings."""
)


async def postmortem_node(state: IncidentState) -> dict[str, Any]:
    """Generate a structured post-mortem from accumulated state."""
    transcript = state.get("transcript", [])
    findings = state.get("findings", [])
    decisions = state.get("decisions", [])

    context_parts: list[str] = []
    if transcript:
        # Truncate transcript to avoid LLM context overflow
        truncated = transcript[-_MAX_TRANSCRIPT_LINES:]
        prefix = ""
        if len(transcript) > _MAX_TRANSCRIPT_LINES:
            prefix = f"[... {len(transcript) - _MAX_TRANSCRIPT_LINES} earlier lines omitted ...]\n"
        context_parts.append("Transcript:\n" + prefix + "\n".join(truncated))
    if findings:
        context_parts.append("Findings:\n" + "\n".join(findings[-20:]))
    if decisions:
        context_parts.append("Decisions:\n" + "\n".join(decisions))

    if not context_parts:
        msg = "Not enough incident data to generate a post-mortem yet."
        return {
            "messages": [AIMessage(content=msg)],
        }

    llm = get_graph_llm()
    messages = [
        POSTMORTEM_SYSTEM_PROMPT,
        HumanMessage(content="\n\n".join(context_parts)),
    ]

    try:
        response = await llm.ainvoke(messages)
        postmortem_text = str(response.content)
    except Exception:
        logger.exception("Post-mortem generation failed")
        msg = "Unable to generate post-mortem at this time."
        return {"messages": [AIMessage(content=msg)]}

    # Save full post-mortem to a dedicated directory
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"postmortem_{ts}.txt"
    try:
        POSTMORTEM_DIR.mkdir(parents=True, exist_ok=True)
        filepath = POSTMORTEM_DIR / filename
        filepath.write_text(postmortem_text, encoding="utf-8")
        logger.info("Post-mortem saved to %s", filepath)
    except Exception:
        logger.exception("Failed to save post-mortem file")
        filepath = Path(filename)

    # Speak a brief summary, store the full text as a finding
    summary = (
        f"I have generated a post-mortem document and saved it "
        f"to {filepath}. Here is a brief overview. " + postmortem_text[:500]
    )

    return {
        "findings": [f"Post-mortem generated: {filename}"],
        "messages": [AIMessage(content=summary)],
    }
