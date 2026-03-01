"""Tests for agent CLI entrypoint — _setup_logging."""

from __future__ import annotations

import logging

from war_room_copilot.core.agent import _setup_logging

# ── _setup_logging ────────────────────────────────────────────────────────────


def test_setup_logging_adds_handler() -> None:
    """Configures war-room-copilot logger with a StreamHandler."""
    app_logger = logging.getLogger("war-room-copilot")
    # Clear any existing handlers from other tests
    app_logger.handlers.clear()

    _setup_logging()

    assert len(app_logger.handlers) == 1
    assert isinstance(app_logger.handlers[0], logging.StreamHandler)

    # Cleanup
    app_logger.handlers.clear()


def test_setup_logging_idempotent() -> None:
    """Second call does not add duplicate handlers."""
    app_logger = logging.getLogger("war-room-copilot")
    app_logger.handlers.clear()

    _setup_logging()
    _setup_logging()

    assert len(app_logger.handlers) == 1

    # Cleanup
    app_logger.handlers.clear()


def test_setup_logging_debug_level() -> None:
    """Logger level is set to DEBUG."""
    app_logger = logging.getLogger("war-room-copilot")
    app_logger.handlers.clear()

    _setup_logging()

    assert app_logger.level == logging.DEBUG

    # Cleanup
    app_logger.handlers.clear()
