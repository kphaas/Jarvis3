#!/bin/zsh
set -euo pipefail

# Mount Documents (read-only)
"/Users/jarvisbrain/jarvis/bin/mount_docs.sh" || true

# Gateway token (Keychain)
TOKEN="$(security find-generic-password -a token -s jarvis.gateway -w)"
export JARVIS_GATEWAY_TOKEN="$TOKEN"

cd /Users/jarvisbrain/jarvis/brain
exec /Users/jarvisbrain/jarvis/brain/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8181
