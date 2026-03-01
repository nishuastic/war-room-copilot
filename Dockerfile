# ── Build stage: install dependencies with uv ────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra all-llm

# Copy source, assets, and README (required by hatchling build), then install the project itself
COPY src/ src/
COPY assets/ assets/
COPY README.md .
RUN uv sync --frozen --no-dev --extra all-llm

# ── Runtime stage: slim image, no build tools ─────────────────────────────────
FROM python:3.12-slim-bookworm

WORKDIR /app

# System deps:
#   libglib2.0-0 — required by LiveKit's native FFI library (liblivekit_ffi.so)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user BEFORE copying files — avoids expensive chown -R later
RUN groupadd --gid 1000 appuser && useradd --uid 1000 --gid appuser --no-create-home appuser

# Copy with correct ownership from the start (no chown -R needed)
COPY --from=builder --chown=appuser:appuser /app/.venv .venv
COPY --from=builder --chown=appuser:appuser /app/src src
COPY --from=builder --chown=appuser:appuser /app/assets assets
COPY --from=builder --chown=appuser:appuser /app/pyproject.toml .

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    HOME=/app \
    APP_DATA_DIR=/app/data

# Persistent data directory (mounted as a Docker volume)
RUN mkdir -p /app/data /app/.models && chown -R appuser:appuser /app/data /app/.models

# Pre-download ML models that Speechmatics downloads at runtime to .models/.
# Without this, the downloads can hang and LiveKit kills the process as unresponsive.
USER appuser
RUN python -c "from urllib.request import urlretrieve; \
urlretrieve('https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx', '/app/.models/silero_vad.onnx'); \
urlretrieve('https://huggingface.co/pipecat-ai/smart-turn-v3/resolve/main/smart-turn-v3.1-cpu.onnx', '/app/.models/smart-turn-v3.1-cpu.onnx')"

EXPOSE 8000

ENTRYPOINT ["python", "-m", "src.war_room_copilot.core.agent"]
CMD ["start"]
