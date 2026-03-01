# War Room Copilot — System Overview

## What It Is

War Room Copilot is a voice-first AI assistant that sits silently in a production incident call, listens to everything, and speaks up when asked. Think of it as the smartest SRE in the room: it never loses track of what was said, can look up live monitoring data, read code, search GitHub, and surface context that would otherwise take 30 minutes to dig up manually.

Engineers address it by name ("Hey Sam, can you check the error rate on the payments service?") and it responds via audio, just like a person on the call.

---

## How It Works

### 1. Listening

The agent joins a **LiveKit** voice room. All audio goes through:

- **Silero VAD** — detects when someone is speaking
- **Speechmatics STT** — transcribes speech to text with **speaker diarization** (it knows _who_ said what)

Every word spoken in the room is captured and stored, regardless of whether the agent is addressed.

### 2. Wake Word

The agent only responds when it hears **"sam"** in a message. Without the wake word, it keeps listening silently and building context.

When "sam" is detected, it buffers up to 1 second for the speaker to finish their sentence, then routes the request.

### 3. Skill Routing

A fast LLM (GPT-4.1-nano) classifies the intent into one of five skills:

| Skill | When Used |
|-------|-----------|
| **debug** | "Why did this break?", "What's causing the 500s?" |
| **ideate** | "What are our options?", "How do we roll this back?" |
| **investigate** | "Check the Datadog APM", "Look at recent commits" |
| **recall** | "What did we decide about the DB timeout?" |
| **general** | Greetings, acknowledgements, off-topic |

It also returns a **confidence score** (0.0–1.0):
- **> 0.7** → agent speaks the response aloud
- **0.4–0.7** → agent runs the skill silently and pushes results to the dashboard only
- **< 0.4** → discarded entirely

### 4. Reasoning and Tools

The agent (GPT-4.1) reasons about the incident and can call tools to look up real data:

**Monitoring**
- Query Datadog metrics (latency, CPU, memory)
- Pull APM traces and error rates
- List triggered monitors/alerts
- Search cloud logs (AWS CloudWatch, GCP, Azure)

**Code and GitHub**
- Search code by query
- Get recent commits and diffs
- List open/closed pull requests
- Search issues
- Read files and get blame info
- Create an incident issue
- Create a revert PR

**Incident Context**
- Get the full service dependency graph and health
- Search SRE runbooks by keyword
- Recall past decisions from this session or previous sessions

### 5. Memory

The agent maintains three memory layers:

- **Short-term** — sliding window of the last ~100 transcript segments (injected into every LLM call as context)
- **Long-term** — [Backboard.io](https://backboard.io) stores key facts, decisions, and summaries that persist across sessions
- **Decision tracking** — every 5 segments, an LLM checks if any decisions, action items, or agreements were made and logs them to the database

### 6. Response

The response is converted to speech via **ElevenLabs TTS** and played back into the LiveKit room.

All interactions — transcript, tool calls, LLM responses, latency — are logged to a local **SQLite** database and made available via a **FastAPI** server.

### 7. Session End

When the last engineer leaves the room, the agent asks 3 structured post-mortem questions via TTS ("What was the root cause?", "What was the impact?", "What will we do differently?") and then closes the session.

---

## What the Frontend Displays

The dashboard at `http://localhost:5173` shows a live view of the incident session. It connects to the API at `http://localhost:8000` via REST polling and Server-Sent Events (SSE) for real-time updates.

### Top Bar

| Element | What it shows |
|---------|--------------|
| Session picker | Dropdown of all past sessions; auto-selects the latest |
| **Turns** pill | Number of speech turns captured this session |
| **Decisions** pill | Number of decisions/action items detected |
| **Events** pill | Number of agent trace events (tool calls, responses, etc.) |
| **LIVE** badge | Green when a session is active and streaming |
| Export button | Downloads a markdown post-mortem for the session |
| Dark mode toggle | Switches between dark and light theme |

If long-term memory was loaded from a previous session, a **memory banner** appears at the top ("Context loaded from N past sessions").

---

### Left Column — Transcript & Agent Trace

A merged, chronological timeline of everything that happened in the session.

**Speech turns** show:
- Speaker identity with a unique color (up to 6 speakers, color-cycled)
- The text they spoke
- Timestamp
- Dimmed appearance for **passive segments** (background speech not directly addressed at the agent)

**Agent trace events** are interleaved inline with the transcript as small badges:

| Badge | Icon | Meaning |
|-------|------|---------|
| Wake word | ◎ | "sam" was detected; skill routing triggered |
| Tool call | → | The agent called a tool (e.g. `query_datadog_apm`) |
| Tool result | ✓ | Tool returned data |
| LLM response | ◈ | The agent's final reply text |
| Latency | ⚡ | Time from wake word to first audio (ms) |

Clicking any trace event expands it to show the raw JSON payload.

Agent responses are highlighted with an accent background so they stand out from human speech.

---

### Right Column — Tabbed Panel

#### Decisions tab

A list of every decision, agreement, or action item detected during the session.

Each decision shows:
- The decision text
- Who said it and when
- A **confidence bar** — color-coded:
  - Green (≥ 85%) — high confidence it was a real decision
  - Yellow (65–84%) — likely a decision
  - Red (< 65%) — possible decision, lower certainty
- A context snippet showing the surrounding conversation

#### Metrics tab

**Cost breakdown** (per session):
- Input token count and cost
- Output token count and cost
- TTS characters and cost
- Total cost in USD

**Latency stats** (wake word → first audio):
- Min, average, max (ms)
- p95 and p99 (ms)

**Usage**:
- Total LLM calls made
- Total tokens used

**Decision analytics**:
- Decision density (decisions per 1,000 characters of transcript)
- Confidence average, median, min/max

**Matched runbooks**:
- SRE runbooks relevant to keywords detected in the session
- Each shows the runbook name, keywords matched, and step-by-step instructions

---

## API Endpoints

The dashboard and any external tool can query the API at `http://localhost:8000`:

| Endpoint | What it returns |
|----------|----------------|
| `GET /sessions` | All sessions (id, start time, room name) |
| `GET /sessions/{id}` | Single session metadata |
| `GET /sessions/{id}/transcript` | All transcript rows with speaker labels |
| `GET /sessions/{id}/decisions` | All detected decisions with confidence |
| `GET /sessions/{id}/metrics` | Token counts, TTS chars, latency stats |
| `GET /sessions/{id}/analytics` | Decision density and confidence trends |
| `GET /sessions/{id}/runbooks` | Runbooks matched to incident keywords |
| `GET /sessions/{id}/summary` | Markdown post-mortem export |
| `GET /insights` | Cross-session stats (total decisions, recent activity) |
| `GET /sessions/{id}/stream` | SSE — live transcript rows as they arrive |
| `GET /sessions/{id}/trace` | SSE — live agent trace events |
| `GET /sessions/latest/id` | Most recent session ID |

---

## Key Files

```
src/war_room_copilot/
├── core/agent.py           Main agent — wake word, routing, memory, session lifecycle
├── skills/
│   ├── router.py           GPT-4.1-nano intent classifier
│   ├── prompts.py          Per-skill prompt suffixes
│   └── investigation.py   Async background investigation (tool-calling loop)
├── tools/
│   ├── github.py           GitHub read/write tools (search, commits, PRs, issues)
│   ├── datadog.py          Datadog metrics, logs, APM, monitors
│   ├── logs.py             AWS / GCP / Azure cloud log queries
│   ├── service_graph.py    Service dependency graph and health
│   ├── runbook.py          Runbook search
│   └── recall.py           Past decision lookup
├── memory/
│   ├── short_term.py       Sliding window of transcript segments
│   ├── long_term.py        Backboard.io wrapper
│   ├── decisions.py        LLM-based decision detection
│   └── db.py               SQLite (sessions, transcript, decisions, agent_trace, metrics)
├── api/
│   ├── main.py             FastAPI app (port 8000, CORS enabled)
│   └── routes/
│       ├── sessions.py     REST endpoints
│       └── stream.py       SSE endpoints
└── config.py               All tunables (models, thresholds, paths, cost rates)

frontend/src/
├── App.tsx                 Layout, topbar, session picker, stats pills
├── components/
│   ├── TranscriptViewer.tsx  Merged transcript + trace timeline
│   ├── DecisionList.tsx      Decision cards with confidence bars
│   ├── AgentTrace.tsx        Collapsible trace event list
│   ├── BusinessMetrics.tsx   Cost and latency breakdown
│   ├── IssueAnalytics.tsx    Decision density and confidence trends
│   └── RunbookPanel.tsx      Matched SRE runbooks
└── hooks/
    ├── useSSE.ts             Generic EventSource wrapper
    └── useSessions.ts        Session list + latest session polling

assets/
├── agent.md                System prompt (Sam's instructions + tools + strategy)
└── k8s_dictionary.json     Custom vocabulary injected into Speechmatics STT

mock_data/
├── service_graph.json      Service topology and health
├── datadog_spans.json      Sample APM spans
└── runbooks.yaml           8 SRE runbooks with keywords and steps
```
