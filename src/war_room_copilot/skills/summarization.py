"""Background summarization runner: single OpenAI call over conversation context."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from ..config import LLM_MODEL

logger = logging.getLogger("war-room-copilot")

_SYSTEM_PROMPT = """\
You are a summarizer for a production incident war room.
Given the recent conversation context, produce a concise structured status update
suitable for being read aloud in a voice call. Use this structure:

1. Known facts — what we know for sure
2. What's been tried — actions taken so far
3. Open unknowns — what we still don't know
4. Suggested next actions — what to do next

Be brief and direct. Skip any section that has nothing to report.\
"""


async def run_summarization(
    context: str,
    user_message: str,
    model: str = LLM_MODEL,
) -> str:
    """Summarize the current incident state from conversation context.

    Args:
        context: Recent conversation context.
        user_message: The user's summarization request.
        model: LLM model to use.

    Returns:
        A voice-ready structured summary.
    """
    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (f"Conversation so far:\n{context[-3000:]}\n\nRequest: {user_message}"),
            },
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content or "Nothing to summarize yet."
