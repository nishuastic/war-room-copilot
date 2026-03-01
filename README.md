# War Room Copilot

Voice-first AI agent for production incidents. Listens to war room calls, reasons with LLMs, interjects with insights, remembers across sessions.

**Your smartest SRE, always in the room — catches your mistakes and surfaces context you'd spend 30 minutes hunting for.**

## Quick Start (One Command)

```bash
make setup   # install all deps (Python + Node)
make dev     # start all 4 services (LiveKit, agent, API, dashboard)
make token   # generate a room token, paste into playground
```

Then open the [LiveKit Agents Playground](https://agents-playground.livekit.io/), set URL to `http://localhost:7880`, paste the token, and connect.

Targets accept colon-style overrides:

```bash
make token room:prod-incident identity:alice ttl:1h
make livekit mode:prod   # uses /etc/livekit.yaml instead of --dev
```

### All Make Commands

| Command | Description |
|---------|-------------|
| `make setup` | Install all dependencies (Python + Node) |
| `make dev` | Start all 4 services (LiveKit, agent, API, dashboard) |
| `make agent` | Start the LiveKit agent only |
| `make console` | Start agent in console mode (no browser needed) |
| `make api` | Start the API server only |
| `make frontend` | Start the dashboard dev server only |
| `make livekit` | Start LiveKit server (`make livekit mode:prod` for production config) |
| `make token` | Generate a room token (`make token room:my-room identity:alice ttl:1h`) |
| `make lint` | Lint with auto-fix (`ruff check`) |
| `make format` | Format code (`ruff format`) |
| `make typecheck` | Type checking (`mypy`) |
| `make test` | Run tests (`pytest`) |
| `make check` | Run full quality pipeline (lint + format + typecheck + test) |

## Manual Setup

### Prerequisites
- macOS (Apple Silicon or Intel)
- Python 3.12+, Node.js 18+
- [Homebrew](https://brew.sh/)
- [uv](https://docs.astral.sh/uv/)
- API keys: OpenAI, Speechmatics (STT + TTS), GitHub (personal access token), Backboard (optional)

### 1. Install dependencies

```bash
uv sync
brew install livekit livekit-cli
cd frontend && npm install && cd ..
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your `OPENAI_API_KEY`, `SPEECHMATICS_API_KEY`, and `GITHUB_TOKEN`. Optionally set `BACKBOARD_API_KEY` for cross-session memory and decision tracking. The LiveKit defaults are already configured for local dev. Also set `GITHUB_ALLOWED_REPOS` in `src/war_room_copilot/config.py` to the repos you want the agent to access.

**GitHub token scope:** The read-only tools (`search_code`, `get_recent_commits`, etc.) need `public_repo` or `repo`. The write tools (`create_github_issue`, `revert_commit`, `close_pull_request`) additionally require the full **`repo`** scope — go to GitHub → Settings → Developer Settings → Personal Access Tokens → edit your token → check **repo**.

**Datadog (optional — all tools fall back to realistic mock data without it):**

1. Sign up at [datadoghq.com](https://datadoghq.com) (free trial works)
2. Get your API key: **Organization Settings → API Keys → New Key**
3. Get your App key: **Organization Settings → Application Keys → New Key**
4. Add to `.env`:
   ```
   DATADOG_API_KEY=<your-api-key>
   DATADOG_APP_KEY=<your-app-key>
   DD_SITE=datadoghq.com   # or us3.datadoghq.com / datadoghq.eu
   ```
5. Seed demo data into your Datadog account (one-time):
   ```bash
   uv run python scripts/seed_datadog.py
   ```
   This pushes APM-style metrics, structured logs, and custom metric series matching the incident scenarios in `mock_data/test_dialogues.md`.
6. Optional — install the Datadog Agent locally for full APM traces via `ddtrace`:
   ```bash
   DD_API_KEY=<key> bash -c "$(curl -L https://install.datadoghq.com/scripts/install_mac_os.sh)"
   ```
   Without the Agent, `seed_datadog.py` will skip APM spans but still push metrics and logs.

> **Datadog MCP:** The official Datadog MCP server (`docs.datadoghq.com/bits_ai/mcp_server`) is allowlist-only preview — not generally available. The agent uses `datadog-api-client` Python SDK directly instead, which gives the same access without needing MCP. If you get allowlist access and want to use Datadog MCP in Claude Code for your own queries, add it to `.claude/mcp.json`.

### 3. Start LiveKit server (Terminal 1)

```bash
livekit-server --dev --bind 0.0.0.0
```

Wait until you see `starting LiveKit server`. Leave it running.

> **Note:** You must run LiveKit natively via Homebrew (not Docker). Docker causes WebRTC connectivity issues with the browser playground.

### 4. Start the agent (Terminal 2)

```bash
uv run python -m src.war_room_copilot.core.agent dev
```

Wait until you see `registered worker`. Leave it running.

### 5. Start the API server (Terminal 3)

```bash
uv run python -m src.war_room_copilot.api.main
```

Wait until you see `DB opened`. Leave it running.

### 6. Start the dashboard (Terminal 4)

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173` — the dashboard auto-connects to the most recent session.

### 7. Generate a room token (Terminal 5)

```bash
lk token create --api-key devkey --api-secret secret --join --room test-room --identity user1 --valid-for 24h
```

Copy the printed access token.

### 8. Connect from the browser

1. Open the [LiveKit Agents Playground](https://agents-playground.livekit.io/) in Chrome
2. Click **Settings** (top right)
3. Set **LiveKit URL** to `http://localhost:7880`
4. Paste the token into the **Token** field
5. Click **Connect**
6. Allow microphone access when prompted
7. Speak — the agent silently listens and accumulates context. Say **"sam"** to trigger a response with full awareness of the conversation so far
8. Watch the dashboard update in real time at `http://localhost:5173`

### Alternative: Console mode (no browser/server needed)

Skip steps 7–8. Console mode uses your Mac's mic and speakers directly — no LiveKit server, no browser, no tokens:

```bash
uv run python -m src.war_room_copilot.core.agent console
```

## How It Works

- Engineer speaks in a LiveKit room
- Speechmatics STT transcribes with speaker diarization and custom vocabulary
- Wake word **"sam"** triggers the AI pipeline
- Skill Router (GPT-4.1-nano) classifies intent; confidence gating decides speak / silent push / discard
- GPT-4.1-mini reasons about the incident and calls tools (GitHub, Datadog, cloud logs, runbooks)
- Speechmatics TTS speaks the response back into the room
- Dashboard shows live transcript, decisions, and agent trace in real time

See [docs/architecture.md](docs/architecture.md) for the full system diagram and component details.

## Dashboard

Read-only observability layer — watch the incident unfold without interrupting the voice flow. Start it with `make dev` (included automatically) or manually with steps 5-6 above.

| Endpoint | Description |
|----------|-------------|
| `GET /sessions` | List all sessions |
| `GET /sessions/{id}/transcript` | All transcript rows |
| `GET /sessions/{id}/decisions` | Captured decisions with confidence |
| `GET /sessions/{id}/stream` | SSE — live transcript |
| `GET /sessions/{id}/trace` | SSE — agent trace (wake word, tool calls, LLM responses) |
| `GET /sessions/latest/id` | Most recent session ID |

Tabs: **Transcript**, **Timeline**, **Agent Trace**, **Decisions**.

## Project Structure

```
src/war_room_copilot/
├── core/
│   └── agent.py          # LiveKit agent entry point (start here)
├── memory/
│   ├── short_term.py     # Sliding window transcript memory
│   ├── long_term.py      # Backboard.io cross-session memory
│   ├── decisions.py      # LLM-based decision detection
│   └── db.py             # SQLite persistence (sessions, transcript, decisions, agent_trace)
├── api/
│   ├── main.py           # FastAPI app (CORS, startup/shutdown, route mounting)
│   └── routes/
│       ├── sessions.py   # REST: GET /sessions, /transcript, /decisions
│       └── stream.py     # SSE: /stream, /trace, /latest/id
├── skills/
│   ├── models.py         # Skill enum + SkillResult model
│   ├── prompts.py        # Per-skill prompt suffixes
│   └── router.py         # Intent classification via GPT-4.1-nano
├── tools/
│   ├── github.py         # GitHub tools (read: search/commits/PRs/blame; write: issues/revert/close-PR)
│   ├── recall.py         # Decision recall tool
│   ├── datadog.py        # Datadog monitoring (metrics, logs, APM, monitors)
│   ├── logs.py           # Multi-cloud logs: AWS CloudWatch/ECS/Lambda, GCP GKE, Azure AKS
│   ├── service_graph.py  # Service dependency graph and health status
│   └── runbook.py        # Runbook search from mock_data/runbooks.yaml
├── config.py             # Centralized configuration
└── models.py             # Pydantic models
assets/
├── agent.md              # Agent system prompt (incident reasoning + tools)
└── k8s_dictionary.json   # Custom vocabulary for Speechmatics STT
frontend/
├── src/
│   ├── App.tsx                     # Session selector + tabbed layout
│   ├── components/
│   │   ├── TranscriptViewer.tsx    # Scrolling transcript with speaker colours
│   │   ├── AgentTrace.tsx          # Collapsible agent events (wake word, tools, LLM)
│   │   ├── IncidentTimeline.tsx    # Merged chronological event stream
│   │   └── DecisionList.tsx        # Decisions with confidence bars
│   └── hooks/
│       ├── useSSE.ts               # Generic EventSource → append state hook
│       └── useSessions.ts          # Fetch /sessions + /latest/id
└── vite.config.ts                  # Vite config with Tailwind + API proxy
```
