# Architecture

## System Overview

War Room Copilot is a voice-first AI agent for production incident war rooms.

```mermaid
flowchart LR
    subgraph LiveKit Room
        User[Engineer on Call]
    end

    subgraph Agent Process
        VAD[Silero VAD]
        STT[Speechmatics STT<br/>Enhanced + Custom Vocab]
        WW{Wake Word?<br/>sam}
        SR[Skill Router<br/>GPT-4.1-nano]
        CG{Confidence<br/>Gate}
        LLM[GPT-4.1-mini<br/>Incident Reasoning]
        Tools[GitHub Tools<br/>search, commits, PRs, blame]
        TTS[ElevenLabs TTS]
    end

    subgraph Memory
        STM[Short-Term Memory<br/>Sliding Window]
        LTM[Backboard.io<br/>Cross-Session Memory]
        DT[Decision Tracker<br/>LLM-based Detection]
        DB[(SQLite WAL<br/>war_room.db)]
    end

    subgraph API Process
        FA[FastAPI<br/>port 8000]
        REST[REST<br/>GET /sessions<br/>GET /sessions/id/transcript<br/>GET /sessions/id/decisions]
        SSE[SSE<br/>GET /sessions/id/stream<br/>GET /sessions/id/trace]
    end

    subgraph Dashboard
        React[React + Vite<br/>port 5173]
        TV[Transcript Viewer]
        AT[Agent Trace]
        IT[Incident Timeline]
        DL[Decision List]
    end

    subgraph External
        GH[GitHub API]
        BB[Backboard API]
    end

    Config[config.py] -.-> STT
    Config -.-> LLM
    Config -.-> TTS
    Config -.-> WW
    Dict[k8s_dictionary.json] -.-> STT
    Prompt[agent.md] -.-> LLM

    User -- audio --> VAD
    VAD -- voice activity --> STT
    STT -- text + speaker ID --> WW
    WW -- "no wake word" --> STM
    WW -- "wake word detected" --> SR
    SR --> CG
    CG -- "< 0.4 discard" --> STM
    CG -- "0.4–0.7 silent" --> BB
    CG -- "> 0.7 speak" --> LLM
    STM -. "context injected" .-> LLM
    STM -- segment --> DB
    STM -- agent_trace --> DB
    STM -- segment --> DT
    DT -- "every 5 segments" --> BB
    DT -- decision --> DB
    DT -- decision --> LTM
    LTM -- store/recall --> BB
    LLM -- "tool call" --> Tools
    LLM -- "recall_decision" --> DB
    LLM -- "recall_decision" --> LTM
    Tools -- "PyGitHub (REST)" --> GH
    GH -- results --> Tools
    Tools -- "tool result" --> LLM
    LLM -- response --> TTS
    TTS -- audio --> User
    DB -- "WAL read" --> FA
    FA --> REST
    FA --> SSE
    REST -- fetch --> React
    SSE -- EventSource --> React
    React --> TV
    React --> AT
    React --> IT
    React --> DL
```

## Current Stage: 7

Stage 7 combines **intent-based skill routing** and **business metrics**. A fast GPT-4.1-nano classifier routes each wake-word request to a skill (debug, ideate, investigate, recall, summarize, or general) with confidence gating: speak (>0.7), silent dashboard push (0.4–0.7), or discard (<0.4). The agent also tracks wake-word → response latency, LLM call counts, token usage, and TTS character counts in a `metrics` DB table. At session end, post-mortem interview mode asks 3 structured questions via TTS. The API exposes four new endpoints: `/metrics`, `/analytics`, `/runbooks`, and `/summary`. The dashboard has a tabbed right panel (Decisions / Metrics) with `BusinessMetrics`, `IssueAnalytics`, and `RunbookPanel` components, agent trace events merged inline into the transcript timeline, and an "Export Post-Mortem" button.

### Features
- Speaker diarization (who said what)
- Speaker identification (recognizes returning speakers via voiceprints saved to `speakers.json`)
- Smart turn detection (knows when someone is done speaking)
- **Wake word activation** — agent silently buffers conversation and only responds when addressed with `"sam"`, then replies with full context awareness
- **Custom vocabulary** for Kubernetes, infrastructure, and incident terms (`assets/k8s_dictionary.json`)
- **Incident reasoning** — asks clarifying questions, identifies unknowns, suggests next steps, flags contradictions
- **GitHub tools** — search code, recent commits, commit diffs, PRs, issues, read files, blame (via PyGitHub REST API)
- **Short-term memory** — structured sliding window of transcript segments with speaker labels and timestamps
- **Long-term memory** — Backboard.io for persistent cross-session recall with auto memory
- **Decision tracking** — LLM-based detection of decisions, action items, and agreements (non-blocking, every 5 segments)
- **SQLite persistence** — local store for call metadata, transcript history, and decisions (`.data/war_room.db`)
- **Recall tool** — `recall_decision` function tool for querying past decisions across sessions
- **Dynamic prompt** with room name, known speakers, and allowed repos injected
- **Skill routing** — LLM-based intent classification (6 skills) with confidence gating (speak / silent dashboard push / discard)
- **Multi-LLM ready** — per-skill model config in `config.py` (all default to GPT-4.1-mini, easily swappable)
- **Centralized config** — all tunables in `config.py`

### Components

| Component | File | Purpose |
|-----------|------|---------|
| Agent | `src/war_room_copilot/core/agent.py` | LiveKit agent entry point, `WarRoomAgent` class |
| Skill Router | `src/war_room_copilot/skills/router.py` | Intent classification via GPT-4.1-nano (debug, ideate, investigate, recall, summarize, general) |
| Skill Prompts | `src/war_room_copilot/skills/prompts.py` | Per-skill prompt suffixes appended to base agent.md |
| GitHub Tools | `src/war_room_copilot/tools/github.py` | 7 `@function_tool` functions for GitHub API access |
| Recall Tool | `src/war_room_copilot/tools/recall.py` | `recall_decision` function tool for querying past decisions |
| Short-Term Memory | `src/war_room_copilot/memory/short_term.py` | Sliding window of `TranscriptSegment` objects |
| Long-Term Memory | `src/war_room_copilot/memory/long_term.py` | Backboard.io wrapper for persistent cross-session memory |
| Decision Tracker | `src/war_room_copilot/memory/decisions.py` | LLM-based decision detection via Backboard |
| SQLite DB | `src/war_room_copilot/memory/db.py` | `IncidentDB` for sessions, transcript, decisions, and agent_trace (WAL mode) |
| API Server | `src/war_room_copilot/api/main.py` | FastAPI server — REST + SSE observability layer |
| REST Routes | `src/war_room_copilot/api/routes/sessions.py` | GET /sessions, /transcript, /decisions, /metrics, /analytics, /runbooks, /summary |
| SSE Routes | `src/war_room_copilot/api/routes/stream.py` | SSE /sessions/{id}/stream, /trace, /latest/id |
| Dashboard | `frontend/` | React + Vite — TranscriptViewer, AgentTrace, DecisionList, BusinessMetrics, IssueAnalytics, RunbookPanel |
| Config | `src/war_room_copilot/config.py` | Centralized configuration (model, voice, paths, repos, memory, cost rates) |
| Runbooks | `mock_data/runbooks.yaml` | 8 SRE runbooks with keywords + steps for keyword-matched suggestions |
| Models | `src/war_room_copilot/models.py` | Pydantic models (`SpeakerMetadata`, `TranscriptSegment`, `Decision`) |
| Prompt | `assets/agent.md` | Agent system instructions (incident reasoning + tools + memory) |
| Dictionary | `assets/k8s_dictionary.json` | Custom vocabulary for Speechmatics STT |

### Data Flow

1. User speaks into LiveKit room
2. Silero VAD detects voice activity
3. Speechmatics transcribes audio to text with speaker labels (using Enhanced mode + custom vocab)
4. `on_user_turn_completed` parses speaker tags into `TranscriptSegment`:
   - Stores segment in short-term memory (sliding window) and SQLite
   - Sends segment to Backboard long-term memory (non-blocking)
   - Fires decision check every 5 segments via Backboard LLM (non-blocking)
5. Wake word check (`"sam"`):
   - **No wake word**: `StopResponse` cancels auto-reply
   - **Wake word detected**: proceeds to skill routing
6. Skill Router (GPT-4.1-nano) classifies intent into one of 6 skills with confidence score
7. Confidence gating:
   - **< 0.4**: discard silently
   - **0.4–0.7**: run skill via Backboard (silent), push result to dashboard via `silent_skill_response` trace
   - **> 0.7**: apply skill-specific prompt suffix, inject context, let pipeline speak
8. Dynamic prompt is built with room name, known speaker names, allowed repos, and skill suffix
9. GPT-4.1-mini reasons about the incident; may call GitHub tools or `recall_decision`
10. `recall_decision` searches SQLite (local decisions) + Backboard (cross-session memory)
11. ElevenLabs TTS converts response to audio
12. Audio sent back to LiveKit room
13. Background task captures speaker voiceprints every 30s for future identification
14. On disconnect: session end time stored, resources cleaned up

## Tech Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Voice framework | LiveKit Agents | Real-time, open-source, good Python SDK |
| STT | Speechmatics (Enhanced) | Enhanced mode for better accuracy, diarization, speaker ID, smart turn detection, custom vocab |
| LLM | GPT-4.1-mini | Fast, cheap, better tool-calling than 4o-mini |
| GitHub tools | PyGitHub (REST) | No local cloning needed, `asyncio.to_thread` for non-blocking |
| TTS | ElevenLabs | Natural voice quality |
| VAD | Silero | Lightweight, runs locally (ONNX) |
| Short-term memory | `collections.deque` | Simple sliding window, O(1) append, bounded size |
| Long-term memory | Backboard.io | LLM routing + auto memory, persistent across sessions |
| Decision detection | LLM via Backboard | No brittle regex patterns, understands context |
| Local persistence | SQLite (aiosqlite) | Lightweight, async, no server needed |
| Skill classification | GPT-4.1-nano | Fast (~300ms), cheap, LLM-based over keywords for intent nuance |
| Config | Plain Python module | Simple, no framework needed, easy to override |
| Models | Pydantic | Type safety at boundaries, validation |

## Planned (Future Stages)

See [PLAN_V0.md](PLAN_V0.md) for the full roadmap: skills router, multi-LLM, auto-interjection, contradiction detection, dashboard, Datadog integration.
