#!/bin/bash
set -euo pipefail

echo "Waiting for Brain to be ready..."
~/jarvis/scripts/wait_for_service.sh http http://100.64.166.22:8182/health 60 || exit 1

echo "Starting dashboard..."
exec /opt/homebrew/bin/node /opt/homebrew/lib/node_modules/serve/build/main.js \
  -s /Users/jarvisendpoint/jarvis/dashboard/build \
  -l 4000
