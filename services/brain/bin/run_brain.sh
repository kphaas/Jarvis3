#!/bin/zsh
set -euo pipefail

# Mount Documents (read-only)
"$HOME/jarvis/bin/mount_docs.sh" 2>/dev/null || true

# Gateway token from Keychain
TOKEN="$(security find-generic-password -a token -s jarvis.gateway.v1 -w)"
export JARVIS_GATEWAY_TOKEN="$TOKEN"

# Brain talks to Gateway over Tailscale
export JARVIS_GATEWAY_BASE="http://100.112.63.25:8282"

cd /Users/jarvisbrain/jarvis/services/brain/brain
exec /Users/jarvisbrain/jarvis/services/brain/.venv/bin/uvicorn app:app \
  --host 0.0.0.0 \
  --port 8182
