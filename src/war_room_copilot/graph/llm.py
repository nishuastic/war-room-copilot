"""LLM factory for LangGraph nodes — returns a LangChain-compatible chat model."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from war_room_copilot.config import get_settings
from war_room_copilot.tools.github_mcp import (
    LLMAuthError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)

logger = logging.getLogger("war-room-copilot.graph.llm")


def classify_llm_error(exc: Exception) -> LLMError:
    """Classify a raw LLM exception into a specific LLMError subtype.

    Inspects the exception message and type to determine if it's a timeout,
    auth failure, or rate limit — then wraps it in the appropriate error class
    so callers get a clear indication of what went wrong.
    """
    msg = str(exc).lower()
    exc_type = type(exc).__name__.lower()

    # Timeout detection
    if "timeout" in msg or "timed out" in msg or "timeouterror" in exc_type:
        return LLMTimeoutError(f"LLM request timed out: {exc}")

    # Auth / key errors
    if any(
        kw in msg for kw in ("authentication", "unauthorized", "401", "invalid api key", "api key")
    ):
        return LLMAuthError(f"LLM authentication failed — check your API key: {exc}")

    # Rate limit detection
    if any(kw in msg for kw in ("rate limit", "429", "too many requests", "quota")):
        return LLMRateLimitError(f"LLM rate limit hit — wait and retry: {exc}")

    # Generic LLM error with the original message preserved
    return LLMError(f"LLM call failed: {exc}")


@lru_cache(maxsize=1)
def get_graph_llm() -> Any:
    """Build a LangChain chat model based on config.

    This is separate from ``llm.create_llm()`` which returns LiveKit plugin
    instances.  Graph nodes need LangChain-compatible models for use inside
    LangGraph.
    """
    cfg = get_settings()
    provider = cfg.llm_provider.lower()
    model = cfg.llm_model

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        model = model or "gpt-4o-mini"
        logger.info("Graph LLM: OpenAI %s", model)
        return ChatOpenAI(model=model, temperature=0)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        model = model or "claude-sonnet-4-20250514"
        logger.info("Graph LLM: Anthropic %s", model)
        return ChatAnthropic(  # type: ignore[call-arg]
            model=model,
            temperature=0,
        )

    if provider == "google":
        from langchain_google_genai import (  # type: ignore[import-untyped]
            ChatGoogleGenerativeAI,
        )

        model = model or "gemini-2.0-flash"
        logger.info("Graph LLM: Google %s", model)
        return ChatGoogleGenerativeAI(  # type: ignore[call-arg]
            model=model,
            temperature=0,
        )

    raise ValueError(
        f"Unsupported graph LLM provider: {provider!r}. "
        "Supported for graph nodes: openai, anthropic, google"
    )
