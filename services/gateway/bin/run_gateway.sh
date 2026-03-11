#!/bin/zsh
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

TOKEN="$(grep '^GATEWAY_TOKEN=' /Users/infranet/jarvis/.secrets | cut -d= -f2 || true)"
if [[ -z "${TOKEN}" ]]; then
  echo "ERROR: No gateway token found" >&2
  exit 2
fi
export JARVIS_GATEWAY_TOKEN="$TOKEN"

cd /Users/infranet/jarvis
exec /Users/infranet/jarvis/.venv/bin/uvicorn \
  services.gateway.app.gateway:app \
  --host 100.112.63.25 \
  --port 8282
