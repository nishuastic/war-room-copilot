"""LLM factory for LangGraph nodes — returns a LangChain-compatible chat model."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from war_room_copilot.config import get_settings

logger = logging.getLogger("war-room-copilot.graph.llm")


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
        return ChatAnthropic(model_name=model, temperature=0)  # type: ignore[call-arg]

    raise ValueError(
        f"Unsupported graph LLM provider: {provider!r}. "
        "Supported for graph nodes: openai, anthropic"
    )
