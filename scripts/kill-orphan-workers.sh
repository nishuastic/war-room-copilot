#!/bin/bash
# Kill orphaned Python processes from previous LiveKit `dev` mode runs.
#
# Problem: LiveKit's multiprocessing.spawn children survive their parent
# (ppid=1) and reconnect to localhost:7880 whenever the Docker LiveKit
# server starts, registering as ghost workers that steal job dispatches
# from the real agent container.
#
# This script finds and kills those orphans before starting Docker.
# Safe to run anytime — only targets orphaned Python processes on :7880.
set -e

PORT=7880

# Find PIDs of processes connected to the LiveKit port.
# lsof may need sudo for other users' processes, but our orphans run as us.
PIDS=$(lsof -t -i :"$PORT" -sTCP:ESTABLISHED 2>/dev/null || true)

if [ -z "$PIDS" ]; then
    exit 0
fi

KILLED=0
for PID in $PIDS; do
    # Only kill Python processes (not Docker, browsers, etc.)
    COMM=$(ps -o comm= -p "$PID" 2>/dev/null || true)
    case "$COMM" in
        *[Pp]ython*|*multiprocessing*)
            # Double-check it's orphaned (ppid=1) or a spawn child
            PPID=$(ps -o ppid= -p "$PID" 2>/dev/null | tr -d ' ' || true)
            if [ "$PPID" = "1" ]; then
                kill "$PID" 2>/dev/null && KILLED=$((KILLED + 1))
            fi
            ;;
    esac
done

if [ "$KILLED" -gt 0 ]; then
    echo "Killed $KILLED orphaned LiveKit worker process(es) on port $PORT"
fi
