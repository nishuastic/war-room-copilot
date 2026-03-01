"""Centralized configuration for War Room Copilot."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]

# LLM
LLM_MODEL = "gpt-4.1-mini"

# Skill router
ROUTER_MODEL = "gpt-4.1-nano"
ROUTER_TIMEOUT = 2.0  # seconds
CONFIDENCE_SPEAK = 0.7
CONFIDENCE_DASHBOARD = 0.4

# Per-skill LLM models — (provider, model) tuples, easily swappable per-skill
SKILL_LLM_MODELS: dict[str, tuple[str, str]] = {
    "debug": ("openai", "gpt-4.1-mini"),
    "ideate": ("openai", "gpt-4.1-mini"),
    "investigate": ("openai", "gpt-4.1-mini"),
    "recall": ("openai", "gpt-4.1-mini"),
    "summarize": ("openai", "gpt-4.1-mini"),
    "general": ("openai", "gpt-4.1-mini"),
}

# TTS
ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

# Speaker identification
FOCUS_SPEAKERS: list[str] = ["S1"]
VOICEPRINT_CAPTURE_INTERVAL = 30  # seconds
VOICEPRINT_INITIAL_DELAY = 15  # seconds

# Wake word
WAKE_WORD = "sam"
WAKE_WORD_BUFFER = 0.25  # seconds to buffer after wake word for sentence completion

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

# Cost rates
GPT4_MINI_INPUT_COST_PER_1K = 0.00015  # $0.15/1M tokens
GPT4_MINI_OUTPUT_COST_PER_1K = 0.0006  # $0.60/1M tokens
ELEVENLABS_COST_PER_CHAR = 0.000003  # rough estimate
CARBON_G_PER_LLM_CALL = 0.2  # ~0.2g CO2 per call

# Runbooks
RUNBOOKS_FILE = PROJECT_ROOT / "mock_data" / "runbooks.yaml"
