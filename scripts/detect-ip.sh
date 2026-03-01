#!/bin/bash
# Detect the host's LAN IP for LiveKit WebRTC (Docker Desktop on Mac).
# Usage:
#   ./scripts/detect-ip.sh          # prints NODE_IP=<ip> for copy-paste into .env
#   eval $(./scripts/detect-ip.sh)  # sets NODE_IP in current shell
set -e

IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')

if [ -z "$IP" ]; then
  echo "ERROR: Could not detect LAN IP. Set NODE_IP manually in .env" >&2
  exit 1
fi

echo "NODE_IP=$IP"
