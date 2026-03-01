"""REST routes for session, transcript, decision, metrics, and analytics data."""

from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI

from ...config import (
    CARBON_G_PER_LLM_CALL,
    GPT4_MINI_INPUT_COST_PER_1K,
    GPT4_MINI_OUTPUT_COST_PER_1K,
    LLM_MODEL,
    RUNBOOKS_FILE,
    SPEECHMATICS_TTS_COST_PER_CHAR,
)
from ...memory.db import IncidentDB
from ..deps import get_db

router = APIRouter()


@router.get("/insights")
async def get_insights(db: IncidentDB = Depends(get_db)) -> dict[str, Any]:
    """Cross-session insights: session count, total decisions, recent decisions."""
    sessions = await db.get_sessions()
    all_decisions: list[Any] = []
    for s in sessions:
        decisions = await db.get_decisions(s["id"])
        for d in decisions:
            all_decisions.append(
                {
                    **d.model_dump(),
                    "session_id": s["id"],
                    "room_name": s["room_name"],
                }
            )
    all_decisions.sort(key=lambda d: d["timestamp"], reverse=True)
    return {
        "session_count": len(sessions),
        "total_decisions": len(all_decisions),
        "recent_decisions": all_decisions[:20],
    }


@router.get("/sessions")
async def list_sessions(db: IncidentDB = Depends(get_db)) -> list[dict[str, Any]]:
    return await db.get_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: int, db: IncidentDB = Depends(get_db)) -> dict[str, Any]:
    session = await db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/sessions/{session_id}/transcript")
async def get_transcript(session_id: int, db: IncidentDB = Depends(get_db)) -> list[dict[str, Any]]:
    return await db.get_transcript(session_id)


@router.get("/sessions/{session_id}/decisions")
async def get_decisions(session_id: int, db: IncidentDB = Depends(get_db)) -> list[dict[str, Any]]:
    decisions = await db.get_decisions(session_id)
    return [d.model_dump() for d in decisions]


@router.get("/sessions/{session_id}/metrics")
async def get_metrics(session_id: int, db: IncidentDB = Depends(get_db)) -> dict[str, Any]:
    session = await db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    raw = await db.get_metrics(session_id)
    transcript = await db.get_transcript(session_id)
    decisions = await db.get_decisions(session_id)

    # Cost calculation
    input_cost = raw["total_input_tokens"] / 1000 * GPT4_MINI_INPUT_COST_PER_1K
    output_cost = raw["total_output_tokens"] / 1000 * GPT4_MINI_OUTPUT_COST_PER_1K
    tts_cost = raw["tts_chars"] * SPEECHMATICS_TTS_COST_PER_CHAR
    total_cost = input_cost + output_cost + tts_cost

    # Carbon estimate
    carbon_g = raw["llm_calls"] * CARBON_G_PER_LLM_CALL

    # Speaker stats
    speaker_turns: dict[str, int] = defaultdict(int)
    speaker_words: dict[str, int] = defaultdict(int)
    speaker_decisions: dict[str, int] = defaultdict(int)

    for row in transcript:
        spk = row["speaker_id"]
        speaker_turns[spk] += 1
        speaker_words[spk] += len(row["text"].split())

    for dec in decisions:
        speaker_decisions[dec.speaker_id] += 1

    all_speakers = set(speaker_turns) | set(speaker_decisions)
    speaker_stats = [
        {
            "speaker_id": spk,
            "turns": speaker_turns.get(spk, 0),
            "words": speaker_words.get(spk, 0),
            "decisions": speaker_decisions.get(spk, 0),
        }
        for spk in sorted(all_speakers)
    ]

    return {
        "cost_usd": round(total_cost, 4),
        "cost_breakdown": {
            "llm_input_usd": round(input_cost, 4),
            "llm_output_usd": round(output_cost, 4),
            "tts_usd": round(tts_cost, 4),
        },
        "carbon_g": round(carbon_g, 2),
        "avg_latency_ms": raw["avg_latency_ms"],
        "llm_calls": raw["llm_calls"],
        "total_input_tokens": raw["total_input_tokens"],
        "total_output_tokens": raw["total_output_tokens"],
        "tts_chars": raw["tts_chars"],
        "speaker_stats": speaker_stats,
    }


@router.get("/sessions/{session_id}/analytics")
async def get_analytics(session_id: int, db: IncidentDB = Depends(get_db)) -> dict[str, Any]:
    session = await db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    transcript = await db.get_transcript(session_id)
    decisions = await db.get_decisions(session_id)

    # Issue categorization by keyword matching
    _db_kw = ["database", "db", "postgres", "mysql", "redis", "query", "connection", "pool"]
    _net_kw = ["network", "dns", "timeout", "latency", "unreachable", "502", "503", "504"]
    _dep_kw = ["deploy", "rollback", "pod", "k8s", "kubernetes", "release", "container", "image"]
    _auth_kw = ["auth", "token", "permission", "forbidden", "unauthorized", "certificate", "ssl"]
    _inf_kw = ["disk", "cpu", "memory", "oom", "node", "storage", "volume", "load"]
    categories: dict[str, dict[str, Any]] = {
        "database": {"keywords": _db_kw, "count": 0},
        "networking": {"keywords": _net_kw, "count": 0},
        "deployment": {"keywords": _dep_kw, "count": 0},
        "auth": {"keywords": _auth_kw, "count": 0},
        "infrastructure": {"keywords": _inf_kw, "count": 0},
    }

    total_turns = len([r for r in transcript if r["speaker_id"] != "sam"])
    speaker_turns: dict[str, int] = defaultdict(int)

    for row in transcript:
        if row["speaker_id"] == "sam":
            continue
        text_lower = row["text"].lower()
        speaker_turns[row["speaker_id"]] += 1
        for cat, cfg in categories.items():
            if any(kw in text_lower for kw in cfg["keywords"]):
                categories[cat]["count"] += 1

    total_matched = sum(c["count"] for c in categories.values()) or 1
    cat_list = [
        {
            "name": name,
            "count": cfg["count"],
            "pct": round(cfg["count"] / total_matched * 100),
        }
        for name, cfg in sorted(categories.items(), key=lambda x: -x[1]["count"])
        if cfg["count"] > 0
    ]

    # Resolution time (session duration)
    started_at = session.get("started_at", 0)
    ended_at = session.get("ended_at")
    resolution_time_s = round(ended_at - started_at) if ended_at else None

    return {
        "categories": cat_list,
        "resolution_time_s": resolution_time_s,
        "total_turns": total_turns,
        "speaker_turns": dict(speaker_turns),
        "total_decisions": len(decisions),
    }


@router.get("/sessions/{session_id}/runbooks")
async def get_runbooks(session_id: int, db: IncidentDB = Depends(get_db)) -> list[dict[str, Any]]:
    session = await db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    transcript = await db.get_transcript(session_id)
    full_text = " ".join(row["text"].lower() for row in transcript)

    if not RUNBOOKS_FILE.exists():
        return []

    with open(RUNBOOKS_FILE) as f:
        runbooks: list[dict[str, Any]] = yaml.safe_load(f) or []

    scored: list[dict[str, Any]] = []
    words = set(re.findall(r"\w+", full_text))
    for rb in runbooks:
        keywords: list[str] = rb.get("keywords", [])
        hits = sum(1 for kw in keywords if kw in words or kw in full_text)
        if hits > 0:
            scored.append(
                {
                    "id": rb["id"],
                    "title": rb["title"],
                    "keywords": keywords,
                    "steps": rb.get("steps", []),
                    "score": hits,
                    "relevance_pct": round(hits / len(keywords) * 100) if keywords else 0,
                }
            )

    scored.sort(key=lambda x: -x["score"])
    return scored[:3]


@router.get("/sessions/{session_id}/summary")
async def get_summary(session_id: int, db: IncidentDB = Depends(get_db)) -> dict[str, str]:
    session = await db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    transcript = await db.get_transcript(session_id)
    decisions = await db.get_decisions(session_id)

    started_at = session.get("started_at", 0)
    ended_at = session.get("ended_at")
    duration = f"{round((ended_at - started_at) / 60, 1)} min" if ended_at else "ongoing"

    transcript_text = "\n".join(f"[{row['speaker_id']}] {row['text']}" for row in transcript[:100])
    decisions_text = "\n".join(
        f"- {d.text} (confidence: {d.confidence:.0%}, by {d.speaker_id})" for d in decisions
    )

    prompt = f"""You are writing a post-mortem for a production incident war room session.

Session: #{session_id} | Room: {session.get("room_name", "unknown")} | Duration: {duration}

TRANSCRIPT (first 100 turns):
{transcript_text or "(no transcript)"}

DECISIONS LOGGED:
{decisions_text or "(none)"}

Write a concise post-mortem in Markdown with these sections:
# Post-Mortem: {session.get("room_name", "Incident")} (Session #{session_id})

## Summary
One paragraph summary of the incident.

## Timeline
Key events in bullet points with approximate times.

## Root Cause
What caused the incident.

## Impact
Who/what was affected and for how long.

## Decisions Made
List key decisions from the session.

## Action Items
Follow-up tasks needed.

## Lessons Learned
What to improve.

Be concise and professional. Use only information from the transcript."""

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # Return a mock summary if no API key
        markdown = f"""# Post-Mortem: {session.get("room_name", "Incident")} (Session #{session_id})

## Summary
Session #{session_id} in room `{session.get("room_name", "unknown")}` lasted {duration} with
{len(transcript)} transcript turns and {len(decisions)} logged decisions.

## Timeline
- Session started
- {len(transcript)} conversation turns recorded
- {len(decisions)} decisions logged

## Root Cause
Analysis not available — OPENAI_API_KEY not configured.

## Decisions Made
{decisions_text or "(none)"}

## Action Items
- Review transcript for follow-up items
- Configure OPENAI_API_KEY to enable AI-generated summaries
"""
        return {"markdown": markdown}

    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
    )
    markdown = response.choices[0].message.content or ""
    return {"markdown": markdown}
