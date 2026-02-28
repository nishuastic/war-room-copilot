"""Platform registry — lazy imports to avoid pulling in unused dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from war_room_copilot.platforms.base import MeetingPlatform

SUPPORTED_PLATFORMS = ("livekit", "google_meet", "zoom")


def get_platform(name: str, **kwargs: Any) -> MeetingPlatform:
    """Return a MeetingPlatform instance for the given name."""
    if name == "livekit":
        from war_room_copilot.platforms.livekit import LiveKitPlatform

        return LiveKitPlatform()

    if name == "google_meet":
        from war_room_copilot.platforms.google_meet import GoogleMeetPlatform

        return GoogleMeetPlatform(meeting_url=str(kwargs.get("meeting_url", "")))

    if name == "zoom":
        from war_room_copilot.platforms.zoom import ZoomPlatform

        return ZoomPlatform(meeting_id=str(kwargs.get("meeting_id", "")))

    raise ValueError(f"Unknown platform: {name!r}. Supported: {', '.join(SUPPORTED_PLATFORMS)}")
