"""Centralized configuration for War Room Copilot."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]

# LLM
LLM_MODEL = "gpt-4.1-mini"

# TTS
ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

# Speaker identification
FOCUS_SPEAKERS: list[str] = ["S1"]
VOICEPRINT_CAPTURE_INTERVAL = 30  # seconds
VOICEPRINT_INITIAL_DELAY = 15  # seconds

# Wake word
WAKE_WORD = "sam"

# File paths
DATA_DIR = PROJECT_ROOT / ".data"
SPEAKERS_FILE = DATA_DIR / "speakers.json"
AGENT_PROMPT_FILE = PROJECT_ROOT / "assets" / "agent.md"
K8S_DICTIONARY_FILE = PROJECT_ROOT / "assets" / "k8s_dictionary.json"

# GitHub
GITHUB_ALLOWED_REPOS: list[str] = ["nishuastic/war-room-copilot"]

# Memory
SHORT_TERM_WINDOW_SIZE = 100  # ~10 min of conversation
DECISION_CHECK_INTERVAL = 5  # check every N new segments
DECISION_CONFIDENCE_THRESHOLD = 0.6

# Backboard
BACKBOARD_ASSISTANT_FILE = DATA_DIR / "backboard_assistant.json"
BACKBOARD_DECISION_ASSISTANT_FILE = DATA_DIR / "backboard_decision_assistant.json"

# SQLite
DB_FILE = DATA_DIR / "war_room.db"
