# War Room Copilot

Voice-first AI agent for production incident war rooms. Joins a LiveKit meeting, transcribes speech with speaker diarization (Speechmatics), reasons with a configurable LLM (OpenAI/Anthropic/Google), and responds via TTS (ElevenLabs). GitHub integration via MCP provides live repo context during incidents.

## Quick Start

```bash
uv sync                                              # install deps
cp .env.example .env                                 # fill in API keys
uv run python -m src.war_room_copilot.core.agent dev # start LiveKit agent
```

For non-OpenAI providers: `uv sync --extra anthropic` or `uv sync --extra all-llm`

## Task Tracking (Beads)

This project uses [beads](https://github.com/steveyegge/beads) for git-backed task tracking. **Always use beads — never markdown TODOs or ad-hoc task lists.** See @AGENTS.md for full workflow details.

**Before any work:** If `bd list` fails, check if the Dolt server is running with `bd dolt test`. If not, start it with `dolt sql-server --port 3307 &` then retry. If beads itself is not initialized, run `bd init && bd setup claude`.

**Workflow for every task:**

1. `bd ready` — check what needs doing
2. `bd create "title" --description="details" -t task -p 2 --json` — create a bead for new work
3. `bd update <id> --status in_progress --json` — claim it
4. Do the work, commit normally
5. `bd close <id> --reason "summary of changes" --json` — when done
6. `bd sync` — save state (also runs automatically via PreCompact hook)

**Multi-step work:** Use `--deps` for subtasks. Link related beads with `bd update <id> --deps relates-to:<other-id>`.
**Discover bugs while working?** `bd create "Found bug" --description="details" -p 1 --deps discovered-from:<parent-id> --json`

## Commands

| Task | Command |
| ---- | ------- |
| Run agent (dev) | `uv run python -m src.war_room_copilot.core.agent dev` |
| Lint + fix | `uv run ruff check src/ --fix` |
| Format | `uv run ruff format src/` |
| Type check | `uv run mypy src/` |
| Tests | `uv run pytest tests/ -v` |
| All checks | `uv run ruff check src/ --fix && uv run ruff format src/ && uv run mypy src/ && uv run pytest tests/ -v` |

## Environment Variables

**LiveKit:** `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
**Speech:** `SPEECHMATICS_API_KEY`, `ELEVEN_API_KEY`
**LLM (pick one):** `OPENAI_API_KEY` (default), `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`
**LLM config:** `LLM_PROVIDER` ("openai"|"anthropic"|"google"), `LLM_MODEL` (empty = provider default)
**GitHub MCP:** `GITHUB_TOKEN`, `DEFAULT_REPO_OWNER`, `DEFAULT_REPO_NAME`
**GitHub MCP tuning:** `GITHUB_MCP_IMAGE`, `GITHUB_MCP_TIMEOUT` (30s), `GITHUB_MCP_CONNECT_TIMEOUT` (10s)

All env vars load from `.env` via pydantic-settings. See @src/war_room_copilot/config.py for full list with defaults.

## Architecture

See @docs/architecture.md for diagrams and detailed design. See @docs/PLAN_V0.md for the roadmap.

**Two-loop architecture:**

- **Voice loop** (real-time): Mic → LiveKit Room → Silero VAD → Speechmatics STT → Voice LLM → ElevenLabs TTS → Speaker
- **Reasoning loop** (async, LangGraph): Voice LLM → Skill Router → [investigate/summarize/recall/respond] → result → Voice LLM

**Core modules:**

- `config.py` — pydantic-settings with `@lru_cache` singleton (`get_settings()`)
- `llm.py` — Voice LLM factory with lazy imports; returns LiveKit-compatible LLM instance
- `models.py` — Pydantic v2 models: `ToolSchema`, `GitHubIssue/PR/Commit`, `RepoContext`
- `core/agent.py` — CLI entrypoint; `parse_known_args` passes extras to LiveKit CLI
- `platforms/base.py` — `MeetingPlatform` Protocol + speaker persistence helpers
- `platforms/livekit.py` — Full implementation: VAD → STT → LLM → TTS + LangGraph bridge (`_invoke_graph`)
- `tools/github_mcp.py` — `GitHubMCPClient` async context manager (Docker stdio transport)
- `tools/github.py` — `get_repo_context()` facade: parallel fetch via `gather(return_exceptions=True)`

**LangGraph modules (`graph/`):**

- `graph/state.py` — `IncidentState` TypedDict: messages, transcript, findings, decisions, speakers
- `graph/llm.py` — LangChain LLM factory (`get_graph_llm()`) for graph nodes (separate from voice LLM)
- `graph/incident_graph.py` — Compiled graph: router → conditional edges → skill nodes → END
- `graph/nodes/skill_router.py` — Intent classification (investigate/summarize/recall/respond)
- `graph/nodes/github_research.py` — Wraps `GitHubMCPClient` for code + issue search
- `graph/nodes/summarize.py` — Incident summary from accumulated state
- `graph/nodes/recall.py` — Memory search for past decisions/discussion
- `graph/nodes/respond.py` — General conversation with incident context

**Platform abstraction:** `MeetingPlatform` Protocol in base.py. `get_platform()` factory in `platforms/__init__.py`. Meet/Zoom are stubs.

## Code Conventions

- `from __future__ import annotations` in every file
- Strict mypy (py312); use `str | None` not `Optional[str]`
- Pydantic `BaseModel` at all boundaries; `BaseSettings` for config
- Logger: `logger = logging.getLogger("war-room-copilot.<module.path>")` with `%s` placeholders (not f-strings)
- Custom exceptions: `WarRoomToolError` → `MCPConnectionError`, `MCPServerError`, `GitHubRateLimitError`
- Async: `AsyncExitStack`, `asyncio.wait_for()` for timeouts, `gather(return_exceptions=True)` for parallel
- Lazy imports in factory functions and `__init__.py` to avoid pulling unused deps
- ruff: target py312, line-length 100, select E/F/I/N/W
- pytest + pytest-asyncio with `asyncio_mode="auto"` (no `@pytest.mark.asyncio` needed)
- Integration tests gated by env var: `@pytest.mark.skipif(not os.getenv("GITHUB_TOKEN"), ...)`

## Common Gotchas

1. **Docker must be running** for GitHub MCP tools — the client spawns `docker run --rm -i` on connect
2. **LiveKit owns the event loop** — `run()` calls `agents.cli.run_app()` which is blocking; do not wrap in `asyncio.run()`
3. **sys.argv rewriting** — `core/agent.py` rewrites sys.argv before calling LiveKit; be careful adding CLI flags
4. **Settings are cached** — `get_settings()` uses `@lru_cache`; call `get_settings.cache_clear()` in tests
5. **`type: ignore` in llm.py** — Anthropic/Google plugins lack stubs; the ignores are intentional
6. **speakers.json is runtime data** — voiceprints saved every 30s by background task; do not commit real data
7. **MCP returns ContentBlocks** — parsers in `tools/github.py` join `.text` fields then `json.loads()`
8. **Optional deps** — Anthropic/Google require `uv sync --extra anthropic` / `--extra google` / `--extra all-llm`
9. **Dolt server required for beads** — run `dolt sql-server --port 3307 &` before using `bd` commands
10. **Two LLM factories** — `llm.create_llm()` returns LiveKit plugins (voice loop); `graph.llm.get_graph_llm()` returns LangChain models (reasoning loop). Both read from the same `LLM_PROVIDER`/`LLM_MODEL` config
11. **Graph LLM is cached** — `get_graph_llm()` uses `@lru_cache`; call `get_graph_llm.cache_clear()` in tests
12. **`_session_state` is module-level** — in `livekit.py`, accumulates across graph invocations within a session; reset on agent restart

## File Maintenance Rules

- Architecture change → update @docs/architecture.md (mermaid diagrams)
- User-facing change → update @README.md (setup/usage)
- New dependency → update @pyproject.toml
- New env var → update this file AND @README.md
- New tool/integration → add to `tools/__init__.py` `__all__` list
- New platform → implement `MeetingPlatform` Protocol, register in `platforms/__init__.py`
- New graph skill → create node in `graph/nodes/`, add to `incident_graph.py`, add routing option in `skill_router.py`
