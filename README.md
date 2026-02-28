# War Room Copilot

Voice-first AI agent for production incidents. Listens to war room calls, reasons with LLMs, interjects with insights, remembers across sessions.

**Your smartest SRE, always in the room — catches your mistakes and surfaces context you'd spend 30 minutes hunting for.**

## Docker Quick Start (Recommended)

The fastest way to get running — no Python, Homebrew, or LiveKit install needed:

```bash
cp .env.example .env       # fill in your API keys
docker compose up --build
```

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

## Manual Setup (Stage 0)

### Prerequisites

- macOS (Apple Silicon or Intel)
- Python 3.12+
- [Homebrew](https://brew.sh/)
- [uv](https://docs.astral.sh/uv/)
- [Docker](https://www.docker.com/) (for GitHub MCP integration)
- API keys: OpenAI, Speechmatics, ElevenLabs
- Optional: GitHub personal access token (for repo context)

### 1. Install dependencies

```bash
uv sync
brew install livekit livekit-cli
```

### 2. Configure environment

```bash
cp .env.example .env
```

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
| `GITHUB_TOKEN` | No | GitHub repo access via MCP server |
| `DEFAULT_REPO_OWNER` | No | Default GitHub org/user for repo context |
| `DEFAULT_REPO_NAME` | No | Default GitHub repo name |

To use a non-default LLM provider, install its plugin extras:

```bash
uv pip install -e ".[anthropic]"   # for Anthropic/Claude
uv pip install -e ".[google]"      # for Google/Gemini
uv pip install -e ".[all-llm]"     # for all providers
```

The LiveKit defaults (`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`) are already configured for local dev.

### 3. Start LiveKit server (Terminal 1)

```bash
livekit-server --dev --bind 0.0.0.0
```

Wait until you see `starting LiveKit server`. Leave it running.

### 4. Start the agent (Terminal 2)

```bash
uv run python -m src.war_room_copilot.core.agent dev
```

Wait until you see `registered worker`. Leave it running.

### 5. Generate a room token (Terminal 3)

```bash
lk token create --api-key devkey --api-secret secret --join --room test-room --identity user1 --valid-for 24h
```

Copy the printed access token.

### 6. Connect from the browser

1. Open the [LiveKit Agents Playground](https://agents-playground.livekit.io/) in Chrome
2. Click **Manual**
3. Set **URL** to `ws://localhost:7880`
4. Paste the token into the **Token** field
5. Click **Connect**
6. Allow microphone access when prompted
7. Speak — the agent will respond

### Alternative: Console mode (no browser/server needed)

Skip steps 3-6 entirely. Console mode uses your Mac's mic and speakers directly — no LiveKit server, no browser, no tokens:

```bash
uv run python -m src.war_room_copilot.core.agent console
```

## GitHub Integration

The agent can access GitHub repos for incident context (issues, PRs, recent commits, code search) via the official [GitHub MCP server](https://github.com/github/github-mcp-server) running in Docker.

### Setup

1. Ensure Docker is running
2. Set `GITHUB_TOKEN` in your `.env` file (needs repo read access)
3. Optionally set `DEFAULT_REPO_OWNER` and `DEFAULT_REPO_NAME` for quick access

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

## Multi-Platform Support

The agent supports swappable meeting platforms via the `--platform` flag. LiveKit is the default; Google Meet and Zoom are stubs ready for implementation.

```bash
# LiveKit (default)
uv run python -m src.war_room_copilot.core.agent dev
uv run python -m src.war_room_copilot.core.agent console

# Google Meet (stub — not yet implemented)
uv run python -m src.war_room_copilot.core.agent --platform google_meet --meeting-url <url>

# Zoom (stub — not yet implemented)
uv run python -m src.war_room_copilot.core.agent --platform zoom --meeting-id <id>
```

See [platforms/base.py](src/war_room_copilot/platforms/base.py) for the `MeetingPlatform` protocol to implement a new platform.

## Architecture

```
Voice Loop (real-time):
  LiveKit Room → Silero VAD → Speechmatics STT → Voice LLM → ElevenLabs TTS → LiveKit Room

Reasoning Loop (async, via LangGraph):
  Voice LLM → Skill Router → [investigate | summarize | recall | respond] → result back to Voice LLM
                                    ↕                                           ↕
                              GitHub MCP (Docker)                     IncidentState (memory)
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
│   ├── __init__.py            # Public API (incident_graph, IncidentState)
│   ├── state.py               # IncidentState TypedDict (shared memory)
│   ├── llm.py                 # LangChain LLM factory for graph nodes
│   ├── incident_graph.py      # Graph definition: router → skill nodes → END
│   └── nodes/
│       ├── skill_router.py    # Intent classification (investigate/summarize/recall/respond)
│       ├── github_research.py # GitHub code + issue search via MCP
│       ├── summarize.py       # Incident summary from accumulated state
│       ├── recall.py          # Memory search for past decisions
│       └── respond.py         # General conversation with context
├── platforms/
│   ├── __init__.py            # Platform registry (lazy imports)
│   ├── base.py                # MeetingPlatform protocol + shared helpers
│   ├── livekit.py             # LiveKit Agents + LangGraph bridge (_invoke_graph)
│   ├── google_meet.py         # Google Meet stub
│   └── zoom.py                # Zoom stub
└── tools/
    ├── __init__.py            # Re-exports
    ├── github_mcp.py          # Async MCP client (Docker stdio transport)
    └── github.py              # High-level facade (get_repo_context)
assets/
└── agent.md                  # Agent system prompt
tests/
└── tools/
    └── test_github_mcp.py    # Unit + integration tests
```

## Development

```bash
# Install with dev dependencies
uv sync --extra dev

# Lint and format
uv run ruff check src/ --fix
uv run ruff format src/

# Type check
uv run mypy src/

# Run tests (unit only — no Docker needed)
uv run pytest tests/ -v -k "not live"

# Run all tests (requires Docker + GITHUB_TOKEN)
uv run pytest tests/ -v
```
