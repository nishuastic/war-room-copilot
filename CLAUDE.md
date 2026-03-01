# War Room Copilot

Voice-first AI agent for production incident war rooms. Joins a LiveKit meeting, transcribes speech with speaker diarization (Speechmatics), reasons with a configurable LLM (OpenAI/Anthropic/Google), and responds via TTS (ElevenLabs). GitHub integration via MCP provides live repo context during incidents.

## Quick Start

Everything runs inside Docker — no local Python, Homebrew, or LiveKit install required:

```bash
cp .env.example .env          # fill in API keys
docker compose up --build      # start everything (LiveKit + GitHub MCP + Agent)
```

For local development (linting, tests, type-checking only):

```bash
uv sync --extra dev            # install dev dependencies
uv run ruff check src/ --fix   # lint
uv run pytest tests/ -v        # tests
```

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
| **Run app** | `make up` (auto-detects LAN IP, kills orphan workers) |
| **Run app (detached)** | `make up-d` |
| **Open Playground** | `make playground` (generates token, copies to clipboard, opens Chrome) |
| **Open Playground (custom room)** | `make playground ROOM=my-room` |
| **View logs** | `make logs` |
| **Generate token** | `make token` |
| **Kill orphan workers** | `make kill-orphans` (auto-runs before `up`/`up-d`/`restart`) |
| **Stop** | `make down` |
| **Full restart** | `make restart` |
| **Stop + wipe volumes** | `docker compose down -v` |
| Lint + fix | `uv run ruff check src/ --fix` |
| Format | `uv run ruff format src/` |
| Type check | `uv run mypy src/` |
| Tests | `uv run pytest tests/ -v` |
| All checks | `uv run ruff check src/ --fix && uv run ruff format src/ && uv run mypy src/ && uv run pytest tests/ -v` |

## Testing the App in Docker (MANDATORY steps)

**Every time you need to test the running app** (e.g. after code changes, after the user asks you to "run the app" or "test it in the browser"), follow ALL of these steps in order. Do NOT skip steps — skipping causes silent failures due to LiveKit gotchas #17, #18, #19, and #21.

```bash
# 1. Full stack teardown (kills LiveKit server + clears stale worker registry)
docker compose down

# 2. Rebuild and start all services
docker compose up --build -d

# 3. Wait for services to be ready
sleep 5
docker compose ps                              # all 3 services must be "running"
docker compose logs agent --tail=5             # confirm agent registered with LiveKit

# 4. Generate a fresh access token
docker compose exec agent python -c "
from livekit.api import AccessToken, VideoGrants
t = AccessToken('devkey', 'secret')
t.with_identity('user1')
t.with_grants(VideoGrants(room_join=True, room='test-room'))
print(t.to_jwt())
"

# 5. Connect via LiveKit Agents Playground
#    - Open a NEW browser tab (never reuse an old Playground tab)
#    - Go to https://agents-playground.livekit.io/
#    - Click "Manual"
#    - Set URL to ws://localhost:7880
#    - Paste the token
#    - Click "Connect"
#    - Use a FRESH room name each time (e.g. test-1, test-2, etc.)

# 6. Verify agent joined
docker compose logs agent --tail=20            # look for "Using OpenAI TTS:" or similar
```

**Why every step matters:**

- Step 1: `docker compose down` (not `restart`) clears LiveKit's worker registry. Without it, LiveKit dispatches to dead workers (gotcha #18).
- Step 2: `--build` ensures code changes are baked into the image. `-d` runs detached.
- Step 5: A **new browser tab** avoids Playground's cached connection state (gotcha #21). A **fresh room name** avoids one-agent-per-room dispatch limits (gotcha #17).

**If the agent connects then immediately disconnects:** Check `/app/data/entrypoint_crash.log` inside the container:

```bash
docker compose exec agent cat /app/data/entrypoint_crash.log
```

## Environment Variables

**LiveKit:** `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` (auto-overridden in Docker Compose)
**Speech:** `SPEECHMATICS_API_KEY`, `ELEVEN_API_KEY`
**LLM (pick one):** `OPENAI_API_KEY` (default), `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`
**LLM config:** `LLM_PROVIDER` ("openai"|"anthropic"|"google"), `LLM_MODEL` (empty = provider default)
**TTS:** `TTS_PROVIDER` ("openai"|"elevenlabs"|"google"), `TTS_MODEL` (empty = provider default)
**GitHub MCP:** `GITHUB_TOKEN`, `DEFAULT_REPO_OWNER`, `DEFAULT_REPO_NAME`
**GitHub MCP tuning:** `GITHUB_MCP_URL` (auto-set in Docker Compose), `GITHUB_MCP_TIMEOUT` (30s), `GITHUB_MCP_CONNECT_TIMEOUT` (10s)

All env vars load from `.env` via pydantic-settings. See @src/war_room_copilot/config.py for full list with defaults.

## Architecture

See @docs/architecture.md for diagrams and detailed design. See @docs/PLAN_V0.md for the roadmap.

**Two-loop architecture:**

- **Voice loop** (real-time): Mic → LiveKit Room → Silero VAD → Speechmatics STT → Voice LLM → ElevenLabs TTS → Speaker
- **Reasoning loop** (async, LangGraph): Voice LLM → Skill Router → [investigate/summarize/recall/respond] → result → Voice LLM

**Core modules:**

- `config.py` — pydantic-settings with `@lru_cache` singleton (`get_settings()`)
- `llm.py` — Voice LLM factory with lazy imports; returns LiveKit-compatible LLM instance
- `tts.py` — TTS factory with lazy imports; returns LiveKit-compatible TTS instance
- `models.py` — Pydantic v2 models: `ToolSchema`, `GitHubIssue/PR/Commit`, `RepoContext`
- `core/agent.py` — CLI entrypoint; `parse_known_args` passes extras to LiveKit CLI
- `platforms/base.py` — `MeetingPlatform` Protocol + speaker persistence helpers
- `platforms/livekit.py` — Full implementation: VAD → STT → LLM → TTS + LangGraph bridge (`_invoke_graph`)
- `tools/github_mcp.py` — `GitHubMCPClient` async context manager (streamable HTTP transport)
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

## Docker Compose Services

| Service | Image | Purpose |
| ------- | ----- | ------- |
| `livekit-server` | `livekit/livekit-server` | WebRTC media server (dev mode) |
| `github-mcp-server` | `ghcr.io/github/github-mcp-server` | GitHub API tools via MCP (HTTP transport) |
| `agent` | Built from `Dockerfile` | War Room Copilot agent |

The agent connects to the MCP sidecar over Docker's internal network — no Docker socket mount, no Docker CLI inside the container.

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

1. **Run everything via `docker compose up`** — the agent, LiveKit server, and GitHub MCP server all run as Docker Compose services. Do not run the agent outside Docker for production use.
2. **LiveKit owns the event loop** — `run()` calls `agents.cli.run_app()` which is blocking; do not wrap in `asyncio.run()`
3. **sys.argv rewriting** — `core/agent.py` rewrites sys.argv before calling LiveKit; be careful adding CLI flags
4. **Settings are cached** — `get_settings()` uses `@lru_cache`; call `get_settings.cache_clear()` in tests
5. **`type: ignore` in llm.py** — Anthropic/Google plugins lack stubs; the ignores are intentional
6. **speakers.json is runtime data** — stored in `/app/data/` (Docker volume `speaker-data`); do not commit
7. **MCP returns ContentBlocks** — parsers in `tools/github.py` join `.text` fields then `json.loads()`
8. **Optional deps** — Anthropic/Google require `uv sync --extra anthropic` / `--extra google` / `--extra all-llm`
9. **Dolt server required for beads** — run `dolt sql-server --port 3307 &` before using `bd` commands
10. **Two LLM factories + TTS factory** — `llm.create_llm()` returns LiveKit plugins (voice loop); `graph.llm.get_graph_llm()` returns LangChain models (reasoning loop); `tts.create_tts()` returns LiveKit TTS plugins. All read from config via `get_settings()`
11. **Graph LLM is cached** — `get_graph_llm()` uses `@lru_cache`; call `get_graph_llm.cache_clear()` in tests
12. **`_session_state` is session-scoped** — in `livekit.py`, reset fresh per session in `_entrypoint()`, protected by `asyncio.Lock`
13. **Docker logging requires `PYTHONUNBUFFERED=1`** — without it, Python block-buffers stdout in non-TTY containers and logs vanish. Always set in Dockerfile.
14. **Use `start` not `dev` in Docker** — `dev` mode uses watchfiles which spawns child processes via `multiprocessing.spawn`; their stdout goes to internal pipes that Docker can't capture. `start` runs directly and logs are visible. Reserve `dev` for local terminal use only.
15. **GitHub MCP is a sidecar** — the MCP server runs in its own container and the agent connects via HTTP (`GITHUB_MCP_URL`). No Docker socket mount needed.
16. **`docker compose restart` does NOT re-read `.env`** — `restart` reuses the existing container with its original environment. To pick up `.env` changes, use `docker compose up -d <service>` which recreates the container. Verify with `docker compose exec agent printenv VAR_NAME`.
17. **LiveKit dev mode: one agent per room** — in `--dev` mode, LiveKit dispatches exactly one agent per room and won't re-dispatch if the room persists. Use a fresh room name or do a full `docker compose down && docker compose up -d` to clear state.
18. **Stale worker dispatch after container recreation** — if you recreate the agent container while LiveKit server keeps running, the server may dispatch jobs to the dead worker from the old container. Fix: full stack restart (`docker compose down && docker compose up -d`).
19. **LiveKit child process crashes are silent** — LiveKit agents use `multiprocessing.forkserver`; child process stdout/stderr goes to internal pipes invisible to Docker. To debug crashes, write to a file in `/app/data/` (Docker volume) and inspect with `docker compose exec agent cat /app/data/debug.log`.
20. **`NODE_IP` in `.env` is your LAN IP** — LiveKit's `--node-ip` flag is set from the `NODE_IP` env var in `.env`. It must be reachable from both the browser (host) and the agent container. Find it with `ipconfig getifaddr en0` or `./scripts/detect-ip.sh`. It changes when you switch WiFi networks, so update `.env` when your IP changes.
21. **LiveKit Agents Playground caches connection state** — after disconnecting, the Manual tab may not show URL/token fields. Open a new browser tab to get a fresh Playground instance.
22. **`github-mcp-server` is distroless** — it has no shell, wget, or curl, so Docker healthchecks that exec commands will fail. Use `service_started` condition instead of `service_healthy` in `depends_on`.
23. **Orphaned local `dev` mode processes steal Docker agent jobs** — running `python -m src.war_room_copilot.core.agent dev` locally creates `multiprocessing.spawn` child processes. If the parent is killed (Ctrl+C in some cases), these children survive as orphans (ppid=1) and reconnect to `localhost:7880` whenever the Docker LiveKit server starts. They register as ghost workers and jobs dispatched to them silently fail. Diagnose with `lsof -i :7880` and kill any stale Python processes: `ps aux | grep "multiprocessing.spawn" | grep war-room | awk '{print $2}' | xargs kill`.

## File Maintenance Rules

- Architecture change → update @docs/architecture.md (mermaid diagrams)
- User-facing change → update @README.md (setup/usage)
- New dependency → update @pyproject.toml
- New env var → update this file AND @README.md
- New tool/integration → add to `tools/__init__.py` `__all__` list
- New platform → implement `MeetingPlatform` Protocol, register in `platforms/__init__.py`
- New graph skill → create node in `graph/nodes/`, add to `incident_graph.py`, add routing option in `skill_router.py`
