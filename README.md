# War Room Copilot

Voice-first AI agent for production incidents. Listens to war room calls, reasons with LLMs, interjects with insights, remembers across sessions.

**Your smartest SRE, always in the room — catches your mistakes and surfaces context you'd spend 30 minutes hunting for.**

## Quick Start (Stage 0 — Echo Agent)

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A running [LiveKit server](https://docs.livekit.io/home/self-hosting/local/)
- OpenAI API key

### Setup

```bash
# Install dependencies
uv sync

# Copy env and fill in your keys
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY

# Start a local LiveKit server (if you don't have one)
# Option A: Docker
docker run --rm -p 7880:7880 -p 7881:7881 -p 7882:7882/udp \
  -e LIVEKIT_KEYS="devkey: secret" \
  livekit/livekit-server

# Option B: livekit-cli
livekit-server --dev
```

### Run the Agent

```bash
uv run python -m src.war_room_copilot.core.agent dev
```

### Connect to the Room

Open the [LiveKit Agents Playground](https://agents-playground.livekit.io/) and connect to your local server. Speak into your mic — the agent will echo back what you say.

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
