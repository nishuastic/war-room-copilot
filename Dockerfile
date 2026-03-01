# ── Build stage: install dependencies with uv ────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source, assets, and README (required by hatchling build), then install the project itself
COPY src/ src/
COPY assets/ assets/
COPY README.md .
RUN uv sync --frozen --no-dev

# ── Runtime stage: slim image, no build tools ─────────────────────────────────
FROM python:3.12-slim-bookworm

WORKDIR /app

# System deps:
#   libglib2.0-0 — required by LiveKit's native FFI library (liblivekit_ffi.so)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv .venv
COPY --from=builder /app/src src
COPY --from=builder /app/assets assets
COPY --from=builder /app/pyproject.toml .

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    HOME=/app \
    APP_DATA_DIR=/app/data

# Persistent data directory (mounted as a Docker volume)
RUN mkdir -p /app/data

# Run as non-root for security
RUN groupadd --gid 1000 appuser && useradd --uid 1000 --gid appuser --no-create-home appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["python", "-m", "src.war_room_copilot.core.agent"]
CMD ["start"]
