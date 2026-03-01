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
import logging
import sys

from dotenv import load_dotenv

load_dotenv()


def _setup_logging() -> None:
    """Configure logging early, before LiveKit's CLI runner takes over.

    LiveKit's ``run_app`` calls its own ``setup_logging()`` which configures the
    root logger.  However, anything that logs *before* that point (imports,
    factory functions) would be silently dropped because the default root logger
    has no handlers and a WARNING level.

    We configure the ``war-room-copilot`` namespace logger with a StreamHandler
    so our application logs are always captured — even if LiveKit's setup hasn't
    run yet or if we're running outside LiveKit (e.g. tests, Google Meet stub).
    LiveKit's root handler will also pick up propagated records, so in practice
    logs appear once (or twice in dev mode, which is fine for debugging).
    """
    app_logger = logging.getLogger("war-room-copilot")
    if app_logger.handlers:
        return  # already configured (e.g. in tests)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.DEBUG)


def main() -> None:
    _setup_logging()

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
