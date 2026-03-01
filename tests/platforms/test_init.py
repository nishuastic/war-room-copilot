"""Tests for platform factory — get_platform registry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from war_room_copilot.platforms import get_platform

# ── get_platform ──────────────────────────────────────────────────────────────


def test_get_platform_unknown_raises() -> None:
    """Unknown platform name raises ValueError."""
    with pytest.raises(ValueError, match="Unknown platform"):
        get_platform("discord")


def test_get_platform_google_meet_passes_url() -> None:
    """Google Meet platform receives the meeting_url kwarg."""
    mock_gm_class = MagicMock()

    with patch(
        "war_room_copilot.platforms.google_meet.GoogleMeetPlatform",
        mock_gm_class,
    ):
        platform = get_platform("google_meet", meeting_url="https://meet.google.com/abc")

    assert platform is not None


def test_get_platform_zoom_passes_id() -> None:
    """Zoom platform receives the meeting_id kwarg."""
    platform = get_platform("zoom", meeting_id="123456")
    assert platform is not None
