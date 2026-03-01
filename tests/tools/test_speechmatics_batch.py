"""Tests for Speechmatics batch API pure helpers."""

from __future__ import annotations

import wave
from io import BytesIO

from war_room_copilot.tools.speechmatics_batch import (
    _build_config,
    create_wav_from_pcm,
    format_enrichment_for_postmortem,
    parse_enrichment,
)

# ── parse_enrichment ─────────────────────────────────────────────────────────


def test_parse_enrichment_full_data() -> None:
    """Full batch result returns all enrichment fields."""
    result = {
        "sentiment_analysis": {
            "summary": {
                "overall_sentiment": "negative",
                "positive_count": 3,
                "negative_count": 7,
                "neutral_count": 5,
            },
            "segments": [
                {
                    "text": "The database is down",
                    "sentiment": "negative",
                    "confidence": 0.95,
                    "speaker": "S1",
                },
            ],
        },
        "topic_detection": {
            "summary": {
                "topics": [
                    {"topic_name": "database outage", "score": 0.92},
                    {"topic_name": "deployment", "score": 0.78},
                ],
            },
        },
        "summary": {"content": "An incident occurred with the database."},
        "chapters": [
            {
                "title": "Initial Report",
                "summary": "Team reported DB issues",
                "start_time": 0,
                "end_time": 120,
            },
            {
                "title": "Investigation",
                "summary": "Checking connection pool",
                "start_time": 120,
                "end_time": 300,
            },
        ],
    }

    enrichment = parse_enrichment(result)

    assert enrichment["sentiment"]["overall"] == "negative"
    assert enrichment["sentiment"]["negative_pct"] == 7
    assert len(enrichment["sentiment"]["segments"]) == 1
    assert enrichment["sentiment"]["segments"][0]["speaker"] == "S1"

    assert len(enrichment["topics"]["topics"]) == 2
    assert enrichment["topics"]["topics"][0]["topic"] == "database outage"

    assert enrichment["summary"] == "An incident occurred with the database."

    assert len(enrichment["chapters"]) == 2
    assert enrichment["chapters"][0]["title"] == "Initial Report"
    assert enrichment["chapters"][1]["end_time"] == 300


def test_parse_enrichment_empty_dict() -> None:
    """Empty result dict returns empty enrichment."""
    enrichment = parse_enrichment({})
    assert enrichment == {}


def test_parse_enrichment_partial_data() -> None:
    """Partial result returns only available fields."""
    result = {
        "summary": {"content": "Quick summary of the call."},
        # No sentiment, topics, or chapters
    }

    enrichment = parse_enrichment(result)

    assert enrichment["summary"] == "Quick summary of the call."
    assert "sentiment" not in enrichment
    assert "topics" not in enrichment
    assert "chapters" not in enrichment


# ── format_enrichment_for_postmortem ─────────────────────────────────────────


def test_format_enrichment_for_postmortem_full() -> None:
    """Full enrichment produces all sections in output."""
    enrichment = {
        "summary": "Database connection pool exhausted during peak traffic.",
        "sentiment": {
            "overall": "negative",
            "positive_pct": 2,
            "negative_pct": 8,
            "neutral_pct": 5,
        },
        "topics": {
            "topics": [
                {"topic": "database", "score": 0.95},
                {"topic": "connection pool", "score": 0.88},
            ],
        },
        "chapters": [
            {
                "title": "Alert Triggered",
                "summary": "PagerDuty alert fired",
                "start_time": 0,
                "end_time": 60,
            },
        ],
    }

    output = format_enrichment_for_postmortem(enrichment)

    assert "## Post-Call Analysis" in output
    assert "### Summary" in output
    assert "Database connection pool" in output
    assert "### Sentiment" in output
    assert "negative" in output.lower()
    assert "### Key Topics" in output
    assert "database" in output
    assert "connection pool" in output
    assert "### Chapters" in output
    assert "Alert Triggered" in output


def test_format_enrichment_for_postmortem_empty() -> None:
    """Empty enrichment produces only the header."""
    output = format_enrichment_for_postmortem({})
    assert "## Post-Call Analysis" in output
    assert "### Summary" not in output
    assert "### Sentiment" not in output


# ── create_wav_from_pcm ──────────────────────────────────────────────────────


def test_create_wav_from_pcm_valid_header() -> None:
    """PCM data wrapped in WAV produces valid WAV with correct params."""
    # Generate 1 second of silence (16-bit mono 16kHz)
    pcm_data = b"\x00\x00" * 16000

    wav_bytes = create_wav_from_pcm(pcm_data, sample_rate=16000, channels=1)

    # Should start with RIFF header
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"

    # Parse with wave module to verify structure
    buf = BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 16000


# ── _build_config ─────────────────────────────────────────────────────────────


def test_build_config_default() -> None:
    """Default config has expected structure and enrichment features enabled."""
    config = _build_config()

    assert config["type"] == "transcription"
    assert config["transcription_config"]["language"] == "en"
    assert config["transcription_config"]["operating_point"] == "enhanced"
    assert config["transcription_config"]["diarization"] == "speaker"
    assert config["transcription_config"]["enable_entities"] is True
    # Enrichment configs should be present (even if empty dicts)
    assert "sentiment_analysis_config" in config
    assert "topic_detection_config" in config
    assert "summarization_config" in config
    assert "auto_chapters_config" in config


def test_build_config_custom_language() -> None:
    """Custom language is passed through."""
    config = _build_config(language="fr")
    assert config["transcription_config"]["language"] == "fr"
