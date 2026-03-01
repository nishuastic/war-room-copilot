"""Background investigation runner: OpenAI tool-calling loop over all available tools."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from openai import AsyncOpenAI

from ..config import INVESTIGATION_CONTEXT_CHARS, LLM_MODEL, MAX_INVESTIGATION_ROUNDS
from ..tools import ALL_TOOLS
from ..tools._registry import get_openai_schemas

logger = logging.getLogger("war-room-copilot")

_TOOL_SCHEMAS = get_openai_schemas(ALL_TOOLS)

_SYSTEM_PROMPT = """\
You are Sam, an SRE investigating a production incident. \
Use the tools to dig into the issue. Chain calls as needed.

When done, give a short verbal summary — like you're reporting to teammates on a call. \
Lead with the most critical finding. 2-3 sentences max. No bullet points, no markdown. \
Talk like an engineer: "p99 is at 12 seconds, pool's maxed out at 100 connections, \
looks like the backboard queries are the bottleneck." Skip filler like "I investigated" \
or "based on my analysis."\
"""


async def run_investigation(
    context: str,
    user_message: str,
    model: str = LLM_MODEL,
) -> str:
    """Run an investigation via an OpenAI tool-calling loop.

    Args:
        context: Recent conversation context for background.
        user_message: The user's investigation request.
        model: LLM model to use.

    Returns:
        A voice-ready summary of the investigation findings.
    """
    client = AsyncOpenAI()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Context from the war room:\n{context[-INVESTIGATION_CONTEXT_CHARS:]}\n\n"
                f"Investigate: {user_message}"
            ),
        },
    ]

    failed_tools: dict[str, str] = {}  # tool_name -> last error message

    for round_num in range(MAX_INVESTIGATION_ROUNDS):
        # Inject hint about previously failed tools so the LLM avoids repeating them
        if failed_tools:
            hint = "IMPORTANT: These tools already failed — do NOT call them with the same args:\n"
            for tool_name, err in failed_tools.items():
                hint += f"  - {tool_name}: {err}\n"
            hint += (
                "Try different arguments or a different tool instead. "
                "If stuck, summarize what you found."
            )
            messages.append({"role": "system", "content": hint})

        response = await client.chat.completions.create(  # type: ignore[call-overload]
            model=model,
            messages=messages,
            tools=_TOOL_SCHEMAS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        msg = choice.message

        # Append assistant turn (preserve tool_calls when present)
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_msg)

        if choice.finish_reason == "stop":
            return msg.content or "Investigation complete — no specific findings."

        if choice.finish_reason != "tool_calls" or not msg.tool_calls:
            break

        # Execute all tool calls in this round concurrently
        tool_results = await asyncio.gather(
            *[_call_tool(tc.id, tc.function.name, tc.function.arguments) for tc in msg.tool_calls]
        )
        messages.extend(tool_results)

        # Track failures so we can warn the LLM on the next round
        for tc, result in zip(msg.tool_calls, tool_results):
            content = result.get("content", "")
            if content.startswith("Tool error (") or content.startswith("Unknown tool:"):
                failed_tools[f"{tc.function.name}({tc.function.arguments})"] = content[:200]

        logger.info(
            "Investigation round %d/%d: called %d tool(s): %s",
            round_num + 1,
            MAX_INVESTIGATION_ROUNDS,
            len(msg.tool_calls),
            ", ".join(tc.function.name for tc in msg.tool_calls),
        )

    return "Investigation reached the tool call limit. Here's what I found: " + (
        next(
            (m.get("content") or "" for m in reversed(messages) if m["role"] == "assistant"),
            "no summary available.",
        )
    )


async def _call_tool(call_id: str, name: str, arguments_json: str) -> dict[str, Any]:
    """Execute one tool call and return the tool-role result message."""
    try:
        args = json.loads(arguments_json)
        tool_fn = ALL_TOOLS.get(name)
        if tool_fn is None:
            result = f"Unknown tool: {name}"
        else:
            result = await tool_fn(**args)
    except Exception as exc:
        result = f"Tool error ({name}): {exc}"
        logger.warning("Investigation tool %r failed: %s", name, exc)

    return {"role": "tool", "tool_call_id": call_id, "content": str(result)}
