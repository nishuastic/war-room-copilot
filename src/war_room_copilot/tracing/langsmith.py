"""LangSmith integration for tracing LLM calls."""

from __future__ import annotations

import logging
import os

from war_room_copilot.config import settings

logger = logging.getLogger("war-room-copilot.tracing")


def setup_langsmith() -> None:
    """Configure LangSmith tracing via environment variables."""
    if not settings.langsmith_api_key:
        logger.info("LangSmith not configured, tracing disabled")
        return

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = "war-room-copilot"
    logger.info("LangSmith tracing enabled")
