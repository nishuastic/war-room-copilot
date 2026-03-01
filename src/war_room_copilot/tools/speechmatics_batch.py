"""Speechmatics batch API client for post-call enrichment.

Provides sentiment analysis, topic detection, and auto-chapters via the
Speechmatics batch transcription REST API.  Used for post-call analysis
after an incident session ends.

API docs: https://docs.speechmatics.com/jobsapi
"""

from __future__ import annotations

import asyncio
import io
import logging
import wave
from typing import Any

import httpx

from war_room_copilot.config import get_settings

logger = logging.getLogger("war-room-copilot.tools.speechmatics_batch")

_BASE_URL = "https://asr.api.speechmatics.com/v2"


def _build_config(language: str = "en") -> dict[str, Any]:
    """Build the batch transcription config with enrichment features enabled."""
    return {
        "type": "transcription",
        "transcription_config": {
            "language": language,
            "operating_point": "enhanced",
            "diarization": "speaker",
            "enable_entities": True,
        },
        "sentiment_analysis_config": {},
        "topic_detection_config": {},
        "summarization_config": {},
        "auto_chapters_config": {},
    }


async def submit_batch_job(
    audio_data: bytes,
    *,
    language: str = "en",
    content_type: str = "audio/wav",
) -> str:
    """Submit audio to Speechmatics batch API for enriched transcription.

    Args:
        audio_data: Raw audio bytes (WAV format preferred).
        language: Language code (default: "en").
        content_type: MIME type of audio.

    Returns:
        Job ID string for polling.
    """
    cfg = get_settings()
    api_key = cfg.speechmatics_api_key
    if not api_key:
        raise ValueError("SPEECHMATICS_API_KEY is required for batch processing")

    config = _build_config(language)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{_BASE_URL}/jobs",
            headers={"Authorization": f"Bearer {api_key}"},
            files={
                "data_file": ("audio.wav", audio_data, content_type),
                "config": (None, __import__("json").dumps(config), "application/json"),
            },
        )
        response.raise_for_status()
        result = response.json()
        job_id = result["id"]
        logger.info("Submitted batch job: %s", job_id)
        return job_id


async def poll_job_status(job_id: str, *, timeout: float = 300.0) -> str:
    """Poll until the batch job completes.

    Args:
        job_id: Speechmatics batch job ID.
        timeout: Max wait time in seconds.

    Returns:
        Job status string ("done" on success).

    Raises:
        TimeoutError: If job doesn't complete within timeout.
    """
    cfg = get_settings()
    api_key = cfg.speechmatics_api_key

    elapsed = 0.0
    interval = 5.0
    async with httpx.AsyncClient(timeout=30.0) as client:
        while elapsed < timeout:
            response = await client.get(
                f"{_BASE_URL}/jobs/{job_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
            status = response.json().get("job", {}).get("status", "unknown")
            if status == "done":
                return status
            if status in ("rejected", "deleted"):
                raise RuntimeError(f"Batch job {job_id} failed with status: {status}")
            await asyncio.sleep(interval)
            elapsed += interval
    raise TimeoutError(f"Batch job {job_id} did not complete within {timeout}s")


async def get_job_result(job_id: str) -> dict[str, Any]:
    """Retrieve the full enriched transcript for a completed batch job.

    Returns a dict with keys: transcript, sentiment_analysis, topics,
    summary, chapters.
    """
    cfg = get_settings()
    api_key = cfg.speechmatics_api_key

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{_BASE_URL}/jobs/{job_id}/transcript",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            params={"format": "json-v2"},
        )
        response.raise_for_status()
        return response.json()


def parse_enrichment(result: dict[str, Any]) -> dict[str, Any]:
    """Parse the batch result into structured enrichment data.

    Returns:
        Dict with: sentiment, topics, summary, chapters — each formatted
        for injection into session state or post-mortem reports.
    """
    enrichment: dict[str, Any] = {}

    # Sentiment analysis
    sentiment = result.get("sentiment_analysis", {})
    if sentiment:
        summary = sentiment.get("summary", {})
        enrichment["sentiment"] = {
            "overall": summary.get("overall_sentiment", "neutral"),
            "positive_pct": summary.get("positive_count", 0),
            "negative_pct": summary.get("negative_count", 0),
            "neutral_pct": summary.get("neutral_count", 0),
            "segments": [
                {
                    "text": seg.get("text", ""),
                    "sentiment": seg.get("sentiment", "neutral"),
                    "confidence": seg.get("confidence", 0),
                    "speaker": seg.get("speaker", "unknown"),
                }
                for seg in sentiment.get("segments", [])[:10]
            ],
        }

    # Topic detection
    topics = result.get("topic_detection", {})
    if topics:
        topic_summary = topics.get("summary", {})
        enrichment["topics"] = {
            "topics": [
                {
                    "topic": t.get("topic_name", ""),
                    "score": t.get("score", 0),
                }
                for t in topic_summary.get("topics", [])
            ],
        }

    # Summarization
    summary_data = result.get("summary", {})
    if summary_data:
        enrichment["summary"] = summary_data.get("content", "")

    # Auto chapters
    chapters = result.get("chapters", [])
    if chapters:
        enrichment["chapters"] = [
            {
                "title": ch.get("title", ""),
                "summary": ch.get("summary", ""),
                "start_time": ch.get("start_time", 0),
                "end_time": ch.get("end_time", 0),
            }
            for ch in chapters
        ]

    return enrichment


def format_enrichment_for_postmortem(enrichment: dict[str, Any]) -> str:
    """Format enrichment data as a text section for post-mortem reports."""
    lines: list[str] = ["## Post-Call Analysis (Speechmatics Batch)"]

    if "summary" in enrichment and enrichment["summary"]:
        lines.append(f"\n### Summary\n{enrichment['summary']}")

    if "sentiment" in enrichment:
        s = enrichment["sentiment"]
        lines.append(
            f"\n### Sentiment\n"
            f"Overall: {s.get('overall', 'N/A')}\n"
            f"Positive segments: {s.get('positive_pct', 0)}, "
            f"Negative: {s.get('negative_pct', 0)}, "
            f"Neutral: {s.get('neutral_pct', 0)}"
        )

    if "topics" in enrichment:
        topics = enrichment["topics"].get("topics", [])
        if topics:
            topic_lines = [f"  - {t['topic']} (score: {t['score']:.2f})" for t in topics[:10]]
            lines.append("\n### Key Topics\n" + "\n".join(topic_lines))

    if "chapters" in enrichment:
        ch_lines = [
            f"  - [{ch['start_time']:.0f}s - {ch['end_time']:.0f}s] "
            f"**{ch['title']}**: {ch['summary']}"
            for ch in enrichment["chapters"]
        ]
        lines.append("\n### Chapters\n" + "\n".join(ch_lines))

    return "\n".join(lines)


async def run_batch_enrichment(audio_data: bytes, *, language: str = "en") -> dict[str, Any]:
    """End-to-end batch enrichment: submit → poll → parse.

    Args:
        audio_data: Raw audio bytes (WAV format).
        language: Language code.

    Returns:
        Parsed enrichment dict with sentiment, topics, summary, chapters.
    """
    job_id = await submit_batch_job(audio_data, language=language)
    await poll_job_status(job_id)
    result = await get_job_result(job_id)
    return parse_enrichment(result)


def create_wav_from_pcm(pcm_data: bytes, *, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wrap raw PCM data in a WAV container for batch API submission."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()
