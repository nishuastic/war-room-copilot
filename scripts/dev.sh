#!/usr/bin/env bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m'
BOLD='\033[1m'

PIDS=()

cleanup() {
    echo ""
    echo -e "${BOLD}Shutting down all services...${NC}"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null
    echo "All services stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM

echo -e "${BOLD}Starting War Room Copilot...${NC}"
echo ""

# Kill any stale processes from a previous run
echo -e "Cleaning up stale processes..."
pkill -f "livekit-server" 2>/dev/null || true
pkill -f "war_room_copilot.core.agent" 2>/dev/null || true
pkill -f "war_room_copilot.api.main" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
# Free ports in case something else is holding them
for port in 7880 8000 5173; do
    lsof -ti:"$port" | xargs kill -9 2>/dev/null || true
done
sleep 1

# 1. LiveKit server (must start first)
echo -e "${RED}[livekit]${NC}  Starting LiveKit server..."
livekit-server --dev --bind 0.0.0.0 2>&1 | grep -v "^$" | sed "s/^/$(printf "${RED}[livekit]${NC} ")/" &
PIDS+=($!)
sleep 2

# 2. Agent
echo -e "${GREEN}[agent]${NC}    Starting agent..."
uv run python -m src.war_room_copilot.core.agent dev 2>&1 | sed "s/^/$(printf "${GREEN}[agent]${NC}   ")/" &
PIDS+=($!)

# 3. API server
echo -e "${BLUE}[api]${NC}      Starting API server..."
uv run python -m src.war_room_copilot.api.main 2>&1 | sed "s/^/$(printf "${BLUE}[api]${NC}     ")/" &
PIDS+=($!)

# 4. Frontend
echo -e "${YELLOW}[frontend]${NC} Starting dashboard..."
(cd frontend && npm run dev) 2>&1 | sed "s/^/$(printf "${YELLOW}[frontend]${NC}")/" &
PIDS+=($!)

sleep 2

echo ""
echo "========================================="
echo "  All services started!"
echo ""
echo "  Dashboard:   http://localhost:5173"
echo "  API:         http://localhost:8000"
echo "  LiveKit:     http://localhost:7880"
echo ""
echo "  Generate token:  make token"
echo "  Playground:      https://agents-playground.livekit.io/"
echo "========================================="
echo ""

wait
