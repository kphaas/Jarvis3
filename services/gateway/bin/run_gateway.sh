#!/bin/zsh
set -euo pipefail

TOKEN="$(security find-generic-password -a token -s jarvis.gateway.v1 -w 2>/dev/null || true)"
if [[ -z "${TOKEN}" ]]; then
  echo "ERROR: jarvis.gateway.v1 token not found in Keychain" >&2
  exit 2
fi
export JARVIS_GATEWAY_TOKEN="$TOKEN"

cd /Users/infranet/jarvis
exec /Users/infranet/jarvis/.venv/bin/uvicorn \
  services.gateway.app.gateway:app \
  --host 100.112.63.25 \
  --port 8282
