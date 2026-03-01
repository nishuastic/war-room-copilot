#!/bin/bash
# Generate a LiveKit token and open the Agents Playground in the browser.
#
# The playground doesn't support URL pre-fill, so this script prints the
# connection details for you to paste into the Manual tab.
#
# Usage:
#   ./scripts/open-playground.sh              # uses default room "war-room"
#   ./scripts/open-playground.sh my-room      # uses custom room name
#   make playground                           # via Makefile
#   make playground ROOM=my-room              # via Makefile with custom room
set -e

ROOM="${1:-war-room}"
IDENTITY="${2:-user1}"
API_KEY="${LIVEKIT_API_KEY:-devkey}"
API_SECRET="${LIVEKIT_API_SECRET:-secret}"

# Generate token inside the agent container
TOKEN=$(docker compose exec -T agent python -c "
from livekit.api import AccessToken, VideoGrants
t = AccessToken('${API_KEY}', '${API_SECRET}')
t.with_identity('${IDENTITY}')
t.with_grants(VideoGrants(room_join=True, room='${ROOM}'))
print(t.to_jwt())
" 2>/dev/null | tr -d '[:space:]')

if [ -z "$TOKEN" ]; then
    echo "ERROR: Failed to generate token. Is the agent container running?" >&2
    echo "Run 'make up-d' first." >&2
    exit 1
fi

echo "========================================"
echo "  LiveKit Agents Playground"
echo "========================================"
echo ""
echo "1. Click 'Manual' in the playground"
echo "2. Paste these values:"
echo ""
echo "  URL:   ws://localhost:7880"
echo "  Token: ${TOKEN}"
echo ""
echo "  Room:     ${ROOM}"
echo "  Identity: ${IDENTITY}"
echo "========================================"

# Copy token to clipboard if possible
if command -v pbcopy &>/dev/null; then
    echo -n "${TOKEN}" | pbcopy
    echo ""
    echo "Token copied to clipboard!"
    echo ""
fi

# Open in Chrome (macOS), falling back to default browser
PLAYGROUND_URL="https://agents-playground.livekit.io"
if [ "$(uname)" = "Darwin" ]; then
    if [ -d "/Applications/Google Chrome.app" ]; then
        open -a "Google Chrome" "${PLAYGROUND_URL}"
    else
        open "${PLAYGROUND_URL}"
    fi
elif command -v google-chrome &>/dev/null; then
    google-chrome "${PLAYGROUND_URL}" &
elif command -v xdg-open &>/dev/null; then
    xdg-open "${PLAYGROUND_URL}"
else
    echo "Open this URL manually: ${PLAYGROUND_URL}"
fi
