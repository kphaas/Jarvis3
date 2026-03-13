#!/bin/bash
set -euo pipefail

echo "Waiting for Dashboard to be ready..."
~/jarvis/scripts/wait_for_service.sh http http://100.87.223.31:4000 60 || exit 1

echo "Waiting for Brain to be ready..."
~/jarvis/scripts/wait_for_service.sh http http://100.64.166.22:8182/health 30 || exit 1

echo "Starting Voice UI..."
cd /Users/jarvisendpoint/jarvis/services/voice
exec /Users/jarvisendpoint/jarvis/services/voice/.venv/bin/uvicorn voice_service:app \
  --host 0.0.0.0 \
  --port 4001
