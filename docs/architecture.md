# Architecture

## System Overview

War Room Copilot is a voice-first AI agent for production incident war rooms.

```mermaid
flowchart LR
    subgraph LiveKit Room
        User[Engineer on Call]
    end

    subgraph Stage 1
        VAD[Silero VAD]
        STT[Speechmatics STT<br/>Enhanced + Custom Vocab]
        WW{Wake Word?<br/>sam}
        Buffer[(Transcript Buffer)]
        LLM[GPT-4o-mini<br/>Incident Reasoning]
        TTS[ElevenLabs TTS]
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
    WW -- "no wake word" --> Buffer
    WW -- "wake word detected" --> LLM
    Buffer -. "context injected" .-> LLM
    LLM -- response --> TTS
    TTS -- audio --> User
```

## Current Stage: 1

The agent joins a LiveKit room, transcribes speech via Speechmatics (with diarization, speaker identification, enhanced operating point, and custom vocabulary for k8s/infra terms), reasons about the incident via GPT-4o-mini, and speaks back via ElevenLabs TTS.

### Features
- Speaker diarization (who said what)
- Speaker identification (recognizes returning speakers via voiceprints saved to `speakers.json`)
- Smart turn detection (knows when someone is done speaking)
- **Wake word activation** — agent silently buffers conversation and only responds when addressed with `"sam"`, then replies with full context awareness
- **Custom vocabulary** for Kubernetes, infrastructure, and incident terms (`assets/k8s_dictionary.json`)
- **Incident reasoning** — asks clarifying questions, identifies unknowns, suggests next steps, flags contradictions
- **Dynamic prompt** with room name and known speakers injected
- **Centralized config** — all tunables in `config.py`

### Components

| Component | File | Purpose |
|-----------|------|---------|
| Agent | `src/war_room_copilot/core/agent.py` | LiveKit agent entry point, `WarRoomAgent` class |
| Config | `src/war_room_copilot/config.py` | Centralized configuration (model, voice, paths, timings) |
| Models | `src/war_room_copilot/models.py` | Pydantic models (`SpeakerMetadata`, `TranscriptSegment`) |
| Prompt | `assets/agent.md` | Agent system instructions (incident reasoning) |
| Dictionary | `assets/k8s_dictionary.json` | Custom vocabulary for Speechmatics STT |

### Data Flow

1. User speaks into LiveKit room
2. Silero VAD detects voice activity
3. Speechmatics transcribes audio to text with speaker labels (using Enhanced mode + custom vocab)
4. `on_user_turn_completed` checks for wake word (`"sam"`):
   - **No wake word**: transcript is buffered silently (`StopResponse` cancels auto-reply)
   - **Wake word detected**: buffered context is injected into the chat context, and the agent responds
5. Dynamic prompt is built with room name and known speaker names
6. GPT-4o-mini reasons about the incident and generates a response
7. ElevenLabs TTS converts response to audio
8. Audio sent back to LiveKit room
9. Background task captures speaker voiceprints every 30s for future identification

## Tech Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Voice framework | LiveKit Agents | Real-time, open-source, good Python SDK |
| STT | Speechmatics (Enhanced) | Enhanced mode for better accuracy, diarization, speaker ID, smart turn detection, custom vocab |
| LLM | GPT-4o-mini | Fast, cheap, good enough for Stage 1 |
| TTS | ElevenLabs | Natural voice quality |
| VAD | Silero | Lightweight, runs locally (ONNX) |
| Config | Plain Python module | Simple, no framework needed, easy to override |
| Models | Pydantic | Type safety at boundaries, validation |

## Planned (Future Stages)

See [PLAN_V0.md](PLAN_V0.md) for the full roadmap: skills router, memory, tools (GitHub, Datadog), dashboard, auto-interjection, contradiction detection.
