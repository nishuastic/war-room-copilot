"""Background investigation runner: OpenAI tool-calling loop over GitHub tools."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from openai import AsyncOpenAI

from ..config import LLM_MODEL
from ..tools.github import (
    get_blame,
    get_commit_diff,
    get_recent_commits,
    list_pull_requests,
    read_file,
    search_code,
    search_issues,
)

logger = logging.getLogger("war-room-copilot")

_MAX_TOOL_ROUNDS = 6

# Map tool name → callable (FunctionTool objects are directly awaitable)
_TOOLS: dict[str, Any] = {
    "search_code": search_code,
    "get_recent_commits": get_recent_commits,
    "get_commit_diff": get_commit_diff,
    "list_pull_requests": list_pull_requests,
    "search_issues": search_issues,
    "read_file": read_file,
    "get_blame": get_blame,
}

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search for code in a GitHub repo. Find errors, functions, or config.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "repo": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_commits",
            "description": "Get recent commits on a branch. Use to see what changed recently.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "branch": {"type": "string"},
                    "count": {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_commit_diff",
            "description": "Get the full diff for a specific commit. Inspect a suspicious change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "commit_sha": {"type": "string"},
                    "repo": {"type": "string"},
                },
                "required": ["commit_sha"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_pull_requests",
            "description": "List recent pull requests. Find merged PRs that caused issues.",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {"type": "string"},
                    "repo": {"type": "string"},
                    "count": {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_issues",
            "description": "Search GitHub issues. Use to find related bugs or past incidents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "repo": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from a GitHub repo. Inspect config, code, or manifests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "repo": {"type": "string"},
                    "ref": {"type": "string"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_blame",
            "description": "Get git blame for a file. Use to find who last touched specific code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "repo": {"type": "string"},
                },
                "required": ["path"],
            },
        },
    },
]

_SYSTEM_PROMPT = """\
You are an investigator for a production incident war room.
Use the available GitHub tools to thoroughly investigate the user's request.
Chain multiple tool calls as needed — check commits, diffs, PRs, and code.
When you have enough evidence, return a concise but complete summary of your findings,
suitable for being read aloud in a voice call. Lead with the most important finding.\
"""


async def run_investigation(
    context: str,
    user_message: str,
    model: str = LLM_MODEL,
) -> str:
    """Run a GitHub investigation via an OpenAI tool-calling loop.

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
                f"Context from the war room:\n{context[-1500:]}\n\nInvestigate: {user_message}"
            ),
        },
    ]

    for round_num in range(_MAX_TOOL_ROUNDS):
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

        logger.info(
            "Investigation round %d/%d: called %d tool(s): %s",
            round_num + 1,
            _MAX_TOOL_ROUNDS,
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
    """Execute one GitHub tool call and return the tool-role result message."""
    try:
        args = json.loads(arguments_json)
        tool_fn = _TOOLS.get(name)
        if tool_fn is None:
            result = f"Unknown tool: {name}"
        else:
            result = await tool_fn(**args)
    except Exception as exc:
        result = f"Tool error ({name}): {exc}"
        logger.warning("Investigation tool %r failed: %s", name, exc)

    return {"role": "tool", "tool_call_id": call_id, "content": str(result)}
