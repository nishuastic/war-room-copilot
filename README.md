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

See all available commands with `make`.

## Manual Setup

### Prerequisites
- macOS (Apple Silicon or Intel)
- Python 3.12+, Node.js 18+
- [Homebrew](https://brew.sh/)
- [uv](https://docs.astral.sh/uv/)
- API keys: OpenAI, Speechmatics, ElevenLabs, GitHub (personal access token), Backboard (optional)

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

Edit `.env` and set your `OPENAI_API_KEY`, `SPEECHMATICS_API_KEY`, `ELEVENLABS_API_KEY`, and `GITHUB_TOKEN`. Optionally set `BACKBOARD_API_KEY` for cross-session memory and decision tracking. The LiveKit defaults are already configured for local dev. Also set `GITHUB_ALLOWED_REPOS` in `src/war_room_copilot/config.py` to the repos you want the agent to access.

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

## Architecture

```
LiveKit Room → Speechmatics STT (diarization + speaker ID + custom vocab) → GPT-4.1-mini (+ GitHub tools) → ElevenLabs TTS → LiveKit Room
```

Stage 1 adds incident reasoning, custom STT dictionary, centralized config, and a wake word (`"sam"`). Stage 2 adds **GitHub tools** (search code, commits, PRs, files, blame) via PyGitHub and upgrades the LLM to **GPT-4.1-mini**. Stage 3 adds **memory and decision tracking** — structured short-term transcript memory, Backboard.io for cross-session recall, LLM-based decision detection, and SQLite persistence. Stage 6 adds a **real-time dashboard** — FastAPI REST + SSE server backed by SQLite WAL, and a React + Vite frontend showing live transcript, agent trace, incident timeline, and decisions.

See [docs/architecture.md](docs/architecture.md) for details.

## Dashboard

The dashboard is a read-only observability layer — watch the incident unfold in real time without interrupting the voice flow.

### Start the API server (Terminal 4)

```bash
uv run python -m src.war_room_copilot.api.main
```

Starts FastAPI on `http://localhost:8000`. Endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /sessions` | List all sessions |
| `GET /sessions/{id}/transcript` | All transcript rows |
| `GET /sessions/{id}/decisions` | Captured decisions with confidence |
| `GET /sessions/{id}/stream` | SSE — live transcript |
| `GET /sessions/{id}/trace` | SSE — agent trace (wake word, tool calls, LLM responses) |
| `GET /sessions/latest/id` | Most recent session ID |

### Start the dashboard (Terminal 5)

```bash
cd frontend && npm install && npm run dev
```

Opens `http://localhost:5173`. The dashboard auto-connects to the most recent active session. Switch between **Transcript**, **Timeline**, **Agent Trace**, and **Decisions** tabs.

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
├── tools/
│   ├── github.py         # GitHub tools (search, commits, PRs, blame)
│   └── recall.py         # Decision recall tool
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
