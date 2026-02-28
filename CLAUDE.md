# War Room Copilot — Developer Guide

## Quick Start
uv sync && uv run python -m src.war_room_copilot.core.agent dev

## Linting & Formatting
uv run ruff check src/ --fix
uv run ruff format src/

## Type Checking
uv run mypy src/

## Tests
uv run pytest tests/ -v

## Environment Variables
LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
OPENAI_API_KEY
SPEECHMATICS_API_KEY
ELEVENLABS_API_KEY
GITHUB_TOKEN
BACKBOARD_API_KEY

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
