"""Pydantic models for type safety at boundaries."""

from pydantic import BaseModel


class SpeakerMetadata(BaseModel):
    label: str
    speaker_identifiers: list[str]


class TranscriptSegment(BaseModel):
    speaker_id: str
    text: str
    timestamp: float
    is_passive: bool = False


class Decision(BaseModel):
    id: str
    text: str
    speaker_id: str
    timestamp: float
    context: str
    confidence: float
