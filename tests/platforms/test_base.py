"""Tests for platform base helpers — speaker I/O and agent prompt loading."""

from __future__ import annotations

import json
from pathlib import Path

import war_room_copilot.platforms.base as base_mod
from war_room_copilot.platforms.base import (
    SpeakerInfo,
    load_agent_prompt,
    load_known_speakers,
    save_speakers,
)

# ── load_known_speakers ──────────────────────────────────────────────────────


def test_load_speakers_missing_file(monkeypatch: object, tmp_path: Path) -> None:
    """No file returns empty list."""

    monkeypatch.setattr(base_mod, "SPEAKERS_FILE", tmp_path / "missing.json")  # type: ignore[attr-defined]
    assert load_known_speakers() == []


def test_load_speakers_malformed_json(monkeypatch: object, tmp_path: Path) -> None:
    """Malformed JSON returns empty list."""
    f = tmp_path / "speakers.json"
    f.write_text("{not valid json")
    monkeypatch.setattr(base_mod, "SPEAKERS_FILE", f)  # type: ignore[attr-defined]
    assert load_known_speakers() == []


def test_load_speakers_not_a_list(monkeypatch: object, tmp_path: Path) -> None:
    """Top-level JSON that is not a list returns empty list."""
    f = tmp_path / "speakers.json"
    f.write_text('{"key": "value"}')
    monkeypatch.setattr(base_mod, "SPEAKERS_FILE", f)  # type: ignore[attr-defined]
    assert load_known_speakers() == []


def test_load_speakers_filters_reserved_labels(monkeypatch: object, tmp_path: Path) -> None:
    """Reserved labels like S0, S1, S99 are filtered out."""
    f = tmp_path / "speakers.json"
    f.write_text(
        json.dumps(
            [
                {"label": "S0", "speaker_identifiers": ["id1"]},
                {"label": "S12", "speaker_identifiers": ["id2"]},
                {"label": "Alice", "speaker_identifiers": ["id3"]},
            ]
        )
    )
    monkeypatch.setattr(base_mod, "SPEAKERS_FILE", f)  # type: ignore[attr-defined]
    speakers = load_known_speakers()
    assert len(speakers) == 1
    assert speakers[0].label == "Alice"


def test_load_speakers_valid(monkeypatch: object, tmp_path: Path) -> None:
    """Valid entries are loaded correctly as SpeakerInfo objects."""
    f = tmp_path / "speakers.json"
    f.write_text(json.dumps([{"label": "Bob", "speaker_identifiers": ["v1", "v2"]}]))
    monkeypatch.setattr(base_mod, "SPEAKERS_FILE", f)  # type: ignore[attr-defined]
    speakers = load_known_speakers()
    assert len(speakers) == 1
    assert speakers[0].label == "Bob"
    assert speakers[0].speaker_identifiers == ["v1", "v2"]


def test_load_speakers_missing_identifiers_skipped(monkeypatch: object, tmp_path: Path) -> None:
    """Entries without speaker_identifiers are skipped."""
    f = tmp_path / "speakers.json"
    f.write_text(json.dumps([{"label": "NoIds"}, {"label": "Ok", "speaker_identifiers": ["x"]}]))
    monkeypatch.setattr(base_mod, "SPEAKERS_FILE", f)  # type: ignore[attr-defined]
    speakers = load_known_speakers()
    assert len(speakers) == 1
    assert speakers[0].label == "Ok"


# ── save_speakers ─────────────────────────────────────────────────────────────


def test_save_speakers_dict_style(monkeypatch: object, tmp_path: Path) -> None:
    """List of dicts is written correctly."""
    f = tmp_path / "speakers.json"
    monkeypatch.setattr(base_mod, "SPEAKERS_FILE", f)  # type: ignore[attr-defined]
    save_speakers([{"label": "Alice", "speaker_identifiers": ["v1"]}])
    data = json.loads(f.read_text())
    assert len(data) == 1
    assert data[0]["label"] == "Alice"


def test_save_speakers_object_style(monkeypatch: object, tmp_path: Path) -> None:
    """SpeakerInfo objects are serialized correctly."""
    f = tmp_path / "speakers.json"
    monkeypatch.setattr(base_mod, "SPEAKERS_FILE", f)  # type: ignore[attr-defined]
    save_speakers([SpeakerInfo(label="Bob", speaker_identifiers=["v1"])])
    data = json.loads(f.read_text())
    assert data[0]["label"] == "Bob"


def test_save_speakers_reserved_label_renamed(monkeypatch: object, tmp_path: Path) -> None:
    """Reserved label S3 is renamed to Speaker_3."""
    f = tmp_path / "speakers.json"
    monkeypatch.setattr(base_mod, "SPEAKERS_FILE", f)  # type: ignore[attr-defined]
    save_speakers([{"label": "S3", "speaker_identifiers": ["v1"]}])
    data = json.loads(f.read_text())
    assert data[0]["label"] == "Speaker_3"


def test_save_speakers_empty_no_write(monkeypatch: object, tmp_path: Path) -> None:
    """Empty speaker list does not create a file."""
    f = tmp_path / "speakers.json"
    monkeypatch.setattr(base_mod, "SPEAKERS_FILE", f)  # type: ignore[attr-defined]
    save_speakers([])
    assert not f.exists()


# ── load_agent_prompt ─────────────────────────────────────────────────────────


def test_load_agent_prompt_exists(monkeypatch: object, tmp_path: Path) -> None:
    """When agent.md exists, its content is returned."""
    agent_file = tmp_path / "agent.md"
    agent_file.write_text("custom prompt")
    monkeypatch.setattr(base_mod, "_PROJECT_ROOT", tmp_path)  # type: ignore[attr-defined]
    # load_agent_prompt uses _PROJECT_ROOT / "assets" / "agent.md"
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "agent.md").write_text("custom prompt")
    assert load_agent_prompt() == "custom prompt"


def test_load_agent_prompt_missing(monkeypatch: object, tmp_path: Path) -> None:
    """When agent.md is missing, the fallback prompt is returned."""
    monkeypatch.setattr(base_mod, "_PROJECT_ROOT", tmp_path)  # type: ignore[attr-defined]
    prompt = load_agent_prompt()
    assert "War Room Copilot" in prompt
