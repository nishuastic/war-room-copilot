# War Room Copilot

Voice-first AI agent for production incidents. Listens to war room calls, reasons with LLMs, interjects with insights, remembers across sessions.

**Your smartest SRE, always in the room — catches your mistakes and surfaces context you'd spend 30 minutes hunting for.**

## Quick Start (Stage 0 — Echo Agent)

### Prerequisites
- macOS (Apple Silicon or Intel)
- Python 3.12+
- [Homebrew](https://brew.sh/)
- [uv](https://docs.astral.sh/uv/)
- OpenAI API key

### 1. Install dependencies

```bash
uv sync
brew install livekit livekit-cli
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your `OPENAI_API_KEY`. The LiveKit defaults are already configured for local dev.

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

### 5. Generate a room token (Terminal 3)

```bash
lk token create --api-key devkey --api-secret secret --join --room test-room --identity user1 --valid-for 24h
```

Copy the printed access token.

### 6. Connect from the browser

1. Open the [LiveKit Agents Playground](https://agents-playground.livekit.io/) in Chrome
2. Click **Settings** (top right)
3. Set **LiveKit URL** to `http://localhost:7880`
4. Paste the token into the **Token** field
5. Click **Connect**
6. Allow microphone access when prompted
7. Speak — the agent will echo back what you say

### Alternative: Console mode (no browser/server needed)

Skip steps 3-6 entirely. Console mode uses your Mac's mic and speakers directly — no LiveKit server, no browser, no tokens:

```bash
uv run python -m src.war_room_copilot.core.agent console
```

## Architecture

```
LiveKit Room → OpenAI Whisper STT → GPT-4o-mini → OpenAI TTS → LiveKit Room
```

## Project Structure

```
src/war_room_copilot/
├── core/
│   └── agent.py          # LiveKit agent entry point (start here)
├── config.py              # Settings and env vars
└── models.py              # Shared Pydantic models
```
