"""Platform abstraction protocol and shared helpers."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger("war-room-copilot.platforms")

_PROJECT_ROOT = Path(__file__).parents[3]
SPEAKERS_FILE = _PROJECT_ROOT / "speakers.json"
RESERVED_LABEL = re.compile(r"^S\d+$")


@dataclass
class SpeakerInfo:
    """Platform-agnostic speaker identifier."""

    label: str
    speaker_identifiers: list[str]


def load_known_speakers() -> list[SpeakerInfo]:
    """Load recognised speakers from speakers.json."""
    if not SPEAKERS_FILE.exists():
        return []
    try:
        with open(SPEAKERS_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError):
        logger.warning("speakers.json is empty or malformed — starting fresh")
        return []
    if not isinstance(data, list):
        return []
    return [
        SpeakerInfo(label=e["label"], speaker_identifiers=e["speaker_identifiers"])
        for e in data
        if e.get("label") and e.get("speaker_identifiers") and not RESERVED_LABEL.match(e["label"])
    ]


def save_speakers(raw_speakers: list[Any]) -> None:
    """Persist speaker voiceprints to speakers.json."""
    data = []
    for speaker in raw_speakers:
        if isinstance(speaker, dict):
            label = speaker.get("label", "")
            ids = speaker.get("speaker_identifiers", [])
        else:
            label, ids = speaker.label, speaker.speaker_identifiers
        if label and ids:
            if RESERVED_LABEL.match(label):
                label = f"Speaker_{label[1:]}"
            data.append({"label": label, "speaker_identifiers": ids})
    if data:
        with open(SPEAKERS_FILE, "w") as f:
            json.dump(data, f, indent=2)


def load_agent_prompt() -> str:
    """Load the system prompt from assets/agent.md."""
    agent_file = _PROJECT_ROOT / "assets" / "agent.md"
    if agent_file.exists():
        return agent_file.read_text()
    return "You are War Room Copilot, an AI assistant in a production incident call. Be concise."


@runtime_checkable
class MeetingPlatform(Protocol):
    """Contract every meeting platform must satisfy.

    ``run()`` joins the meeting, sets up the audio pipeline, runs the agent
    loop, and blocks until the meeting ends or is interrupted.

    ``run()`` is intentionally sync — LiveKit manages its own event loop.
    Async platforms should use ``asyncio.run()`` at the call site.
    """

    def run(self) -> None: ...

    async def shutdown(self) -> None: ...
