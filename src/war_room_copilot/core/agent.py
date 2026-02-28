"""War Room Copilot — CLI entrypoint.

Usage:
    # LiveKit (default) — extra args forwarded to LiveKit CLI
    python -m src.war_room_copilot.core.agent dev
    python -m src.war_room_copilot.core.agent console

    # Google Meet / Zoom (stubs — not yet implemented)
    python -m src.war_room_copilot.core.agent --platform google_meet --meeting-url <url>
    python -m src.war_room_copilot.core.agent --platform zoom --meeting-id <id>
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(description="War Room Copilot")
    parser.add_argument(
        "--platform",
        choices=["livekit", "google_meet", "zoom"],
        default="livekit",
        help="Meeting platform to use (default: livekit)",
    )
    parser.add_argument("--meeting-url", help="Meeting URL (for Google Meet)")
    parser.add_argument("--meeting-id", help="Meeting ID (for Zoom)")

    # parse_known_args lets LiveKit-specific args (dev, console) pass through
    args, remaining = parser.parse_known_args()

    from war_room_copilot.platforms import get_platform

    if args.platform == "livekit":
        # LiveKit's CLI runner parses sys.argv itself.
        # Reconstruct argv so it sees only the pass-through args.
        sys.argv = [sys.argv[0], *remaining]

    platform = get_platform(
        args.platform,
        meeting_url=args.meeting_url or "",
        meeting_id=args.meeting_id or "",
    )
    platform.run()


if __name__ == "__main__":
    main()
