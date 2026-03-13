#!/bin/bash
set -euo pipefail

echo "Waiting for Voice UI to be ready..."
~/jarvis/scripts/wait_for_service.sh http http://100.87.223.31:4001/v1/voice/status 60 || exit 1

echo "Starting Avatar service..."
cd /Users/jarvisendpoint/jarvis/services/avatar
exec /Users/jarvisendpoint/jarvis/services/avatar/.venv/bin/uvicorn avatar_service:app \
  --host 0.0.0.0 \
  --port 4002
