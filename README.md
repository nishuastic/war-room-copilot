# War Room Copilot

Voice-first AI agent for production incidents. Listens to war room calls, reasons with LLMs, interjects with insights, remembers across sessions.

**Your smartest SRE, always in the room — catches your mistakes and surfaces context you'd spend 30 minutes hunting for.**

## Quick Start

Everything runs inside Docker Compose — no local Python, Homebrew, or LiveKit install needed:

```bash
cp .env.example .env       # fill in your API keys
make up                    # auto-detects LAN IP, starts everything
```

This starts three services:

| Service | Purpose |
| --- | --- |
| `livekit-server` | WebRTC media server (dev mode) |
| `github-mcp-server` | GitHub API tools via MCP (HTTP sidecar) |
| `agent` | War Room Copilot voice agent + dashboard API |

Then generate a token and connect:

```bash
docker compose exec agent python -c "
from livekit.api import AccessToken, VideoGrants
t = AccessToken('devkey', 'secret')
t.with_identity('user1')
t.with_grants(VideoGrants(room_join=True, room='test-room'))
print(t.to_jwt())
"
```

Open the [LiveKit Agents Playground](https://agents-playground.livekit.io/), click **Manual**, set the URL to `ws://localhost:7880`, paste the token, and click **Connect**.

## Environment Variables

Edit `.env` and set your API keys:

| Variable | Required | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | No | LLM provider: `openai` (default), `anthropic`, or `google` |
| `LLM_MODEL` | No | Model name (defaults: `gpt-4o-mini`, `claude-sonnet-4-20250514`, `gemini-2.0-flash`) |
| `OPENAI_API_KEY` | Yes* | OpenAI API key (*required when using OpenAI provider) |
| `ANTHROPIC_API_KEY` | No* | Anthropic API key (*required when using Anthropic provider) |
| `GOOGLE_API_KEY` | No* | Google API key (*required when using Google provider) |
| `SPEECHMATICS_API_KEY` | Yes | Speech-to-text with diarization |
| `ELEVEN_API_KEY` | Yes | Text-to-speech (ElevenLabs plugin expects this name) |
| `GITHUB_TOKEN` | No | GitHub repo access via MCP sidecar |
| `DEFAULT_REPO_OWNER` | No | Default GitHub org/user for repo context |
| `DEFAULT_REPO_NAME` | No | Default GitHub repo name |
| `NODE_IP` | Yes | Your Mac's LAN IP for WebRTC (`ipconfig getifaddr en0`) |

LiveKit defaults (`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`) and the GitHub MCP URL (`GITHUB_MCP_URL`) are auto-configured inside Docker Compose.

## GitHub Integration

The agent accesses GitHub repos for incident context (issues, PRs, recent commits, code search) via the official [GitHub MCP server](https://github.com/github/github-mcp-server) running as a Docker Compose sidecar.

### Setup

1. Set `GITHUB_TOKEN` in your `.env` file (needs repo read access)
2. Optionally set `DEFAULT_REPO_OWNER` and `DEFAULT_REPO_NAME` for quick access
3. Run `docker compose up --build` — the MCP sidecar starts automatically

### Usage (Python)

```python
from war_room_copilot.tools import GitHubMCPClient, get_repo_context

# Fetch repo context (issues, PRs, commits)
async with GitHubMCPClient() as client:
    ctx = await get_repo_context(client, owner="myorg", repo="myapp")
    print(ctx.as_prompt_context())  # compact text for LLM injection

# Call any of the 51 GitHub MCP tools directly
async with GitHubMCPClient() as client:
    result = await client.call_tool("search_code", {
        "owner": "myorg", "repo": "myapp", "query": "database connection"
    })
```

## Architecture

```text
Docker Compose:
  ┌─────────────────┐  ┌──────────────────────┐  ┌──────────────┐
  │  livekit-server  │  │  github-mcp-server   │  │    agent     │
  │  :7880 (WebRTC)  │  │  :8090 (HTTP/MCP)    │  │  :8000 (SSE) │
  └────────┬─────────┘  └──────────┬───────────┘  └──┬───────────┘
           │                       │                   │
           └───────────────────────┴───────────────────┘
                        Docker internal network

Voice Loop (real-time):
  LiveKit Room → Silero VAD → Speechmatics STT → Voice LLM → ElevenLabs TTS → LiveKit Room

Reasoning Loop (async, via LangGraph):
  Voice LLM → Skill Router → [investigate | summarize | recall | respond] → result back to Voice LLM
                                    ↕                                           ↕
                              GitHub MCP (sidecar)                   IncidentState (memory)
```

See [docs/architecture.md](docs/architecture.md) for detailed diagrams, Mermaid charts, and tech decisions.

## Project Structure

```
src/war_room_copilot/
├── config.py                 # Settings (pydantic-settings, auto .env loading)
├── llm.py                    # Voice LLM factory (OpenAI / Anthropic / Google)
├── models.py                 # Shared Pydantic models (GitHubIssue, RepoContext, etc.)
├── core/
│   └── agent.py              # CLI entrypoint (--platform flag)
├── graph/                     # LangGraph reasoning layer
│   ├── state.py               # IncidentState TypedDict (shared memory)
│   ├── llm.py                 # LangChain LLM factory for graph nodes
│   ├── incident_graph.py      # Graph definition: router → skill nodes → END
│   └── nodes/
│       ├── skill_router.py    # Intent classification
│       ├── github_research.py # GitHub code + issue search via MCP
│       ├── summarize.py       # Incident summary from accumulated state
│       ├── recall.py          # Memory search for past decisions
│       └── respond.py         # General conversation with context
├── platforms/
│   ├── base.py                # MeetingPlatform protocol + shared helpers
│   ├── livekit.py             # LiveKit Agents + LangGraph bridge
│   ├── google_meet.py         # Google Meet stub
│   └── zoom.py                # Zoom stub
├── api/
│   └── main.py                # FastAPI SSE dashboard endpoint
└── tools/
    ├── github_mcp.py          # Async MCP client (streamable HTTP transport)
    └── github.py              # High-level facade (get_repo_context)
```

## Development

Linting, testing, and type-checking run locally (not inside Docker):

```bash
# Install dev dependencies
uv sync --extra dev

# Lint and format
uv run ruff check src/ --fix
uv run ruff format src/

# Type check
uv run mypy src/

# Run tests (unit only)
uv run pytest tests/ -v -k "not live"

# Run all tests (requires GitHub MCP sidecar running)
uv run pytest tests/ -v
```

## Data Persistence

Runtime data (voiceprints, postmortems) is stored in a Docker named volume (`speaker-data`) mounted at `/app/data/`. To inspect or back up:

```bash
docker compose exec agent ls /app/data/
```

To wipe all data: `docker compose down -v`

## Troubleshooting

### Changed `.env` but agent still uses old values

`docker compose restart` reuses the existing container environment. Use `docker compose up -d agent` to recreate the container with fresh env vars. Verify with:

```bash
docker compose exec agent printenv LLM_PROVIDER
```

### Agent doesn't join after reconnecting to the same room

LiveKit dev mode dispatches one agent per room. Once dispatched, reconnecting to the same room won't trigger a new agent. Either use a fresh room name or do a full restart:

```bash
docker compose down && docker compose up -d
```

### Agent connects briefly then disconnects (stale worker)

If you recreate the agent container while LiveKit server keeps running, the server may dispatch jobs to the dead worker from the old container. Fix with a full stack restart:

```bash
docker compose down && docker compose up -d
```

### No agent logs visible at all (silent crash)

LiveKit agents use `multiprocessing.forkserver` — child process stdout/stderr goes to internal pipes invisible to Docker. To debug, write to a file in the Docker volume:

```python
# Temporary debug wrapper in _entrypoint
import traceback
try:
    # ... existing code ...
except Exception:
    with open("/app/data/agent_crash.log", "w") as f:
        traceback.print_exc(file=f)
    raise
```

Then inspect: `docker compose exec agent cat /app/data/agent_crash.log`

### WebRTC not connecting (no audio/video)

`NODE_IP` in `.env` must be your host's current LAN IP (reachable from both the browser and the agent container). Detect and update:

```bash
./scripts/detect-ip.sh          # prints NODE_IP=<your-ip>
# Copy the output into .env, then:
docker compose up -d livekit-server   # recreate with new IP
```

This IP changes when you switch WiFi networks.

### LiveKit Playground doesn't show URL/token fields after disconnecting

The Playground caches connection state in memory. Open a new browser tab to get a fresh instance.
