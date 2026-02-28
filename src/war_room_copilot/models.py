"""Shared Pydantic models — the contract between all modules."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Transcript ──────────────────────────────────────────────────────
class TranscriptChunk(BaseModel):
    speaker: str = "unknown"
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_final: bool = False


class TranscriptWindow(BaseModel):
    chunks: list[TranscriptChunk] = []

    @property
    def full_text(self) -> str:
        return "\n".join(f"[{c.speaker}] {c.text}" for c in self.chunks)


# ── Skills ──────────────────────────────────────────────────────────
class SkillType(str, Enum):
    DEBUG = "debug"
    IDEATE = "ideate"
    INVESTIGATE = "investigate"
    RECALL = "recall"
    SUMMARIZE = "summarize"
    CONTRADICT = "contradict"


class SkillResult(BaseModel):
    skill: SkillType
    content: str
    confidence: float = 1.0
    should_speak: bool = True
    reasoning: str = ""
    tool_calls: list[dict[str, Any]] = []


# ── Interjection ────────────────────────────────────────────────────
class InterjectionDecision(BaseModel):
    should_interject: bool = False
    confidence: float = 0.0
    content: str = ""
    reasoning: str = ""
    contradictions: list[str] = []


# ── Decisions / Memory ──────────────────────────────────────────────
class Decision(BaseModel):
    id: str = ""
    summary: str
    speaker: str = "unknown"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    context: str = ""
    tags: list[str] = []


class MemoryEntry(BaseModel):
    key: str
    value: str
    source: str = "conversation"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Tools ───────────────────────────────────────────────────────────
class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = {}
    result: Any = None
    duration_ms: float = 0.0


# ── Dashboard Events (WebSocket) ────────────────────────────────────
class EventType(str, Enum):
    TRANSCRIPT = "transcript"
    AGENT_RESPONSE = "agent_response"
    TOOL_CALL = "tool_call"
    INTERJECTION = "interjection"
    DECISION = "decision"
    TRACE = "trace"
    METRIC = "metric"
    TIMELINE = "timeline"


class DashboardEvent(BaseModel):
    type: EventType
    data: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Business Metrics ────────────────────────────────────────────────
class CostEntry(BaseModel):
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class IncidentSummary(BaseModel):
    title: str = ""
    timeline: list[dict[str, Any]] = []
    decisions: list[Decision] = []
    root_cause: str = ""
    action_items: list[str] = []
    duration_minutes: float = 0.0
