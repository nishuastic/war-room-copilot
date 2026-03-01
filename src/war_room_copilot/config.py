"""Centralized configuration for War Room Copilot."""

import subprocess
from pathlib import Path


def _find_project_root() -> Path:
    """Find project root robustly — works in LiveKit subprocess too."""
    # First try __file__ based resolution
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "pyproject.toml").exists():
        return candidate
    # Fall back to git root (handles subprocess CWD changes)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except Exception:
        pass
    # Last resort: walk up from CWD
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return candidate


PROJECT_ROOT = _find_project_root()

# LLM
LLM_MODEL = "gpt-4.1"

# Skill router
ROUTER_MODEL = "gpt-4.1-mini"
ROUTER_TIMEOUT = 2.0  # seconds
CONFIDENCE_SPEAK = 0.7
CONFIDENCE_DASHBOARD = 0.4

# Per-skill LLM models — (provider, model) tuples, easily swappable per-skill
SKILL_LLM_MODELS: dict[str, tuple[str, str]] = {
    "debug": ("openai", "gpt-4.1"),
    "ideate": ("openai", "gpt-4.1"),
    "investigate": ("openai", "gpt-4.1"),
    "recall": ("openai", "gpt-4.1"),
    "general": ("openai", "gpt-4.1"),
}

# TTS
SPEECHMATICS_TTS_VOICE = "jack"  # Options: sarah (UK F), theo (UK M), megan (US F), jack (US M)

# Speaker identification
FOCUS_SPEAKERS: list[str] = ["S1"]
VOICEPRINT_CAPTURE_INTERVAL = 30  # seconds
VOICEPRINT_INITIAL_DELAY = 15  # seconds

# Wake word
WAKE_WORD = "sam"
WAKE_WORD_BUFFER = 1.0  # seconds to buffer after wake word for sentence completion

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
SPEECHMATICS_TTS_COST_PER_CHAR = 0.000011  # $0.011/1k chars
CARBON_G_PER_LLM_CALL = 0.2  # ~0.2g CO2 per call

# Tool output
TOOL_OUTPUT_CHAR_LIMIT = 2000

# Context windows
ROUTER_CONTEXT_CHARS = 2000
INVESTIGATION_CONTEXT_CHARS = 1500

# GitHub
GITHUB_RESULT_LIMIT = 10
GITHUB_COMMIT_MSG_TRUNCATE = 80

# Investigation
MAX_INVESTIGATION_ROUNDS = 6

# Mock data
MOCK_DATA_DIR = PROJECT_ROOT / "mock_data"

# Runbooks
RUNBOOKS_FILE = MOCK_DATA_DIR / "runbooks.yaml"

# Datadog
# Get these from: datadoghq.com → Organization Settings → API Keys / Application Keys
# DD_SITE: e.g. "datadoghq.com" (US1), "us3.datadoghq.com", "datadoghq.eu" (EU)
# When not set, all Datadog tools return mock data from mock_data/datadog_spans.json
DATADOG_API_KEY = ""  # override via DATADOG_API_KEY env var
DATADOG_APP_KEY = ""  # override via DATADOG_APP_KEY env var
DD_SITE = "datadoghq.com"  # override via DD_SITE env var
