# War Room Copilot — Hackathon Implementation Plan V0

## Context
Voice-first AI agent for production incidents. Listens to calls, reasons with LLMs, interjects with insights, remembers across sessions. Single developer workflow, staged from trivial to advanced.

**One-liner**: "Your smartest SRE, always in the room — catches your mistakes and surfaces context you'd spend 30 minutes hunting for."

## Architecture
```
LiveKit Room → Speechmatics STT (enhanced, diarization, custom dict)
  → Transcript Buffer → Skill Router → Backboard.io (multi-LLM + memory)
  → Tools: GitHub MCP, Datadog MCP, mock logs
  → Decision: speak | silent | dashboard update
  → TTS → LiveKit Room
  → FastAPI WebSocket → React Dashboard (transcript, trace, timeline, business metrics)
```

## Auto-Interjection: Technical Flow
The agent doesn't just respond when addressed — it monitors passively and interjects when it detects high-value moments:

```
1. Speechmatics streams transcript chunks continuously
2. Every N seconds (or on silence detection), accumulated transcript sent to "Contradict" skill
3. Contradict skill system prompt instructs LLM to:
   - Track all factual claims made by each speaker (timestamps, content)
   - Detect logical contradictions ("You said deploy was at 2pm, but earlier you said 3pm")
   - Detect circular reasoning ("You've returned to the same hypothesis 3 times")
   - Correlate claims against tool data (e.g., speaker says "DB is fine" but metrics show high latency)
4. LLM returns: {should_interject: bool, confidence: float, content: str, reasoning: str}
5. Only if confidence > 0.7 AND speaker has paused (silence > 1.5s):
   - Play audio "ping"
   - Speak interjection via TTS
   - Push reasoning to dashboard trace
6. If confidence 0.4-0.7: silently push insight to dashboard (visible but not spoken)
7. If confidence < 0.4: discard

Key: The contradict skill runs in PARALLEL with normal conversation handling.
It has access to the full sliding window (last 5-10 min) to catch contradictions across time.
```

## Integration Strategy
- **GitHub**: Clone target repo locally, use **GitHub MCP server** so the agent has native tool access (search, blame, diff, PR, issues)
- **Datadog**: Push mock spans/metrics to Datadog, use **Datadog MCP server** to query them — same flow as production
- **Other logs**: Mock tool calls returning realistic data
- **Observability**: **LangSmith** (better ecosystem, LangChain native, production-grade)

## Project Structure (Scalable)
```
war-room-copilot/
├── CLAUDE.md                     # Dev workflow, linting, testing, file maintenance
├── README.md                     # User-facing: setup, usage, demo instructions
├── docs/
│   └── architecture.md           # Mermaid diagrams, tech decisions, updated with plan changes
├── pyproject.toml
├── src/
│   └── war_room_copilot/
│       ├── __init__.py
│       ├── config.py             # Settings, env vars, thresholds
│       ├── models.py             # Pydantic models (shared contract)
│       ├── core/
│       │   ├── __init__.py
│       │   ├── agent.py          # LiveKit agent entry point
│       │   ├── stt.py            # Speechmatics config
│       │   ├── tts.py            # TTS config
│       │   └── pipeline.py       # Main orchestration loop
│       ├── skills/
│       │   ├── __init__.py
│       │   ├── router.py         # Intent classification → skill dispatch
│       │   ├── debug.py
│       │   ├── ideate.py
│       │   ├── investigate.py
│       │   ├── recall.py
│       │   ├── summarize.py
│       │   └── contradict.py     # Passive monitoring + auto-interjection
│       ├── memory/
│       │   ├── __init__.py
│       │   ├── short_term.py     # Sliding window transcript buffer
│       │   ├── long_term.py      # Backboard.io persistent memory
│       │   └── decisions.py      # Decision tracking + recall
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── github.py         # GitHub MCP tool wrappers
│       │   ├── datadog.py        # Datadog MCP tool wrappers
│       │   ├── logs.py           # Mock log queries
│       │   ├── service_graph.py
│       │   └── runbook.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── main.py           # FastAPI app
│       │   ├── ws.py             # WebSocket: transcript, traces, events
│       │   └── routes.py         # REST endpoints
│       └── tracing/
│           ├── __init__.py
│           └── langsmith.py      # LangSmith integration
├── frontend/
│   ├── package.json
│   └── src/
│       ├── App.tsx
│       ├── components/
│       │   ├── Transcript.tsx
│       │   ├── AgentTrace.tsx     # Full reasoning/tool call trace
│       │   ├── Timeline.tsx
│       │   ├── DecisionLog.tsx
│       │   ├── ServiceGraph.tsx
│       │   ├── RunbookPanel.tsx
│       │   └── BusinessMetrics.tsx # Credits, cost, carbon, issue analytics
│       └── hooks/
│           └── useWebSocket.ts
├── mock_data/
│   ├── datadog_spans.json
│   ├── application_logs.json
│   ├── service_graph.json
│   └── runbooks.yaml
└── tests/
    ├── test_skill_router.py
    ├── test_memory.py
    └── test_tools.py
```

---

## Stages (Single Developer Flow)

### Stage 0: Bare Minimum LiveKit Agent (Hours 0-1.5)
**Goal**: A LiveKit agent that joins a room and echoes back what you say.

- Install `livekit-agents`, `livekit-plugins-openai`
- Create `src/war_room_copilot/core/agent.py` from LiveKit starter template
- Use LiveKit's built-in STT (OpenAI Whisper) + TTS (OpenAI) — NOT Speechmatics yet
- Agent joins room, transcribes speech, responds with "I heard you say: {text}"
- Verify: join room from browser, speak, hear echo

### Stage 1: Speechmatics + Basic Reasoning (Hours 1.5-4)
**Goal**: Switch to Speechmatics STT, add basic LLM reasoning.

- Install `livekit-plugins-speechmatics`
- Configure: enhanced mode, diarization, custom dictionary (k8s terms, service names)
- Replace Whisper with Speechmatics as STT provider
- Add OpenAI GPT as reasoning LLM — simple incident-focused system prompt
- Agent now actually reasons about what you say, not just echoes
- Create `models.py` with shared Pydantic models
- Create `config.py` for env vars and thresholds
- Verify: describe an incident, get a contextual response

### Stage 2: Tools + GitHub Integration (Hours 4-7)
**Goal**: Agent can query real data via tools.

- Set up GitHub MCP server pointing at cloned repo
- Create tool wrappers in `tools/github.py` (search code, recent commits, PR diffs, blame)
- Create mock tools: `query_logs`, `query_metrics`, `service_graph`
- Wire tools into OpenAI function calling
- Create `mock_data/` files with realistic Datadog spans, logs, service graph
- Verify: "What changed in checkout-service recently?" → agent queries GitHub, responds with real commits

### Stage 3: Memory + Decision Tracking (Hours 7-10)
**Goal**: Agent remembers across the conversation and across sessions.

- Implement `memory/short_term.py`: sliding window of transcript chunks with speaker labels
- Set up Backboard.io for persistent memory (cross-session recall)
- Implement `memory/decisions.py`: detect decision patterns, store with speaker/timestamp
- Create `recall_decision` tool
- Verify: make a decision mid-conversation, ask about it later, get accurate recall

### Stage 4: Skill Router + Multi-LLM (Hours 10-13)
**Goal**: Different conversation intents routed to specialized skills.

- Implement `skills/router.py`: classify intent from transcript
- Create skill prompts: debug, ideate, investigate, recall, summarize
- Route via Backboard.io to different LLMs per skill
- Implement confidence-gated output (>0.7 speak, 0.4-0.7 dashboard only, <0.4 discard)
- Verify: shift between debugging and brainstorming, notice different response styles

### Stage 5: Auto-Interjection + Contradiction Detection (Hours 13-16)
**Goal**: Agent passively monitors and interjects when it catches errors.

- Implement `skills/contradict.py`: runs in parallel, analyzes transcript for contradictions
- Trigger word detection: pattern match "hey copilot" on transcript for direct-address mode
- Audio "ping" before interjection
- Silence detection: only interject during natural pauses (>1.5s)
- Cross-reference claims against tool data (speaker says "DB is fine" → check metrics)
- Verify: deliberately make contradictory statements, agent catches and flags them

### Stage 6: Dashboard + API (Hours 16-19)
**Goal**: Real-time web dashboard showing everything.

- FastAPI app with WebSocket for real-time streaming
- React frontend (Vite + TailwindCSS):
  - Live transcript with color-coded speakers
  - Agent trace viewer: every step (STT → skill → LLM → tools → response → decision)
  - Incident timeline (auto-generated from conversation)
  - Decision log with speaker attribution
  - Service dependency graph
- LangSmith integration for tracing all LLM calls
- Verify: open dashboard alongside call, see real-time updates

### Stage 7: Business Metrics + Polish (Hours 19-22)
**Goal**: Demo-ready, business-focused dashboard.

- Dashboard additions:
  - Credits/cost tracker ($ spent on LLM calls)
  - Carbon footprint estimate
  - Issue analytics (types of issues discussed, frequency, resolution time)
  - Runbook suggestion panel
- Post-mortem interview mode
- Auto-rollback suggestion
- One-click incident summary export
- Latency optimization: target <3s end-to-end
- Rehearse demo scripts

### Stage 8: Datadog + Advanced Integrations (Hours 22-23)
**Goal**: Real monitoring data.

- Push mock data to Datadog
- Set up Datadog MCP server
- Replace mock metric/log tools with Datadog MCP calls
- Verify: agent queries real Datadog dashboards

### Stage 9: Stretch (Hours 23-24)
- Platform connectors: Discord bot, Slack (Recall.ai), Google Meet, Zoom
- Multi-incident memory ("this looks like Jan 15th outage")
- Custom voice persona
- Ambient standup mode

---

## Future Enhancements

### 1. Smart Wake Word Classification
- **Current:** simple substring match (`"sam" in text`) — causes false positives ("Sam mentioned it") and misses context
- **Future:** use a fast LLM to classify "addressing Sam" vs "mentioning Sam"
- **Options researched:**
  - **Groq Llama 3.1 8B** (~140-160ms, OpenAI-compatible API, recommended)
  - **GPT-4.1-nano** (~360-450ms, no extra deps, fallback)
  - **Local SetFit** (~10-20ms, zero network, needs training examples)
- Only runs when "sam" is in the text (fast-path skip for 99% of turns)

### 2. Audio Feedback During Tool Calls
- **Current:** dead silence while agent processes tool calls (GitHub search, etc.)
- **Future:** play a subtle thinking tone or say "Let me check that..." while tools execute
- Use LiveKit's session event hooks (`on_tool_call_start` / `on_tool_call_end`)

### 3. Passive Speech Filtering
- **Current:** `is_passive` is parsed from Speechmatics tags but not used in wake word detection
- **Future:** passive speech should never trigger the wake word — only buffer it for context

---

## CLAUDE.md Contents (to create)
```markdown
# War Room Copilot — Developer Guide

## Quick Start
uv sync && python -m src.war_room_copilot.core.agent

## Linting & Formatting
uv run ruff check src/ --fix
uv run ruff format src/

## Type Checking
uv run mypy src/

## Tests
uv run pytest tests/ -v

## Environment Variables
LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
SPEECHMATICS_API_KEY
OPENAI_API_KEY
BACKBOARD_API_KEY
LANGSMITH_API_KEY
GITHUB_TOKEN

## File Maintenance Rules
- After ANY architecture change: update docs/architecture.md (mermaid diagrams)
- After ANY user-facing change: update README.md (setup/usage instructions)
- After adding new dependencies: update pyproject.toml
- After adding new env vars: update this section AND README.md
- Keep README.md focused on: what it is, how to install, how to run, how to demo
- Keep docs/architecture.md focused on: system design, data flow, tech decisions

## Code Quality Checklist (run before committing)
1. uv run ruff check src/ --fix
2. uv run ruff format src/
3. uv run mypy src/
4. uv run pytest tests/ -v
5. Check if architecture changed → update docs/architecture.md
6. Check if usage changed → update README.md
```

## Scalability Check (end of each stage)
After completing each stage, verify:
1. Can a new developer understand the structure by reading CLAUDE.md + README.md?
2. Are all modules loosely coupled (skills, tools, memory are independent)?
3. Can you swap STT/LLM/TTS providers without touching other modules?
4. Are Pydantic models used at all boundaries?
5. Is the docs/architecture.md still accurate?

## Key Dependencies
```toml
dependencies = [
    "livekit-agents>=1.0",
    "livekit-plugins-speechmatics",
    "livekit-plugins-openai",
    "openai",
    "pydantic>=2.0",
    "fastapi",
    "uvicorn[standard]",
    "websockets",
    "aiosqlite",
    "pygithub",
    "langsmith",
    "httpx",
    "ruff",
]
```

## Verification (Full Flow)
1. `python -m src.war_room_copilot.core.agent` → joins LiveKit room
2. `uvicorn src.war_room_copilot.api.main:app` → starts backend
3. `cd frontend && npm run dev` → starts dashboard
4. Join LiveKit room → speak incident → agent responds with tool-backed insights
5. Dashboard: live transcript, agent trace (all steps), timeline, decisions, business metrics
6. "Hey copilot, what did we decide about caching?" → Backboard memory recall
7. Make contradictory statements → agent auto-interjects with correction
8. Agent queries real GitHub for commits/PRs
