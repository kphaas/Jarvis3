#!/bin/zsh
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "Waiting for Postgres..."
~/jarvis/scripts/wait_for_service.sh postgres || exit 1

echo "Waiting for Tailscale..."
for i in {1..60}; do
  TS_IP=$(tailscale ip -4 2>/dev/null || true)
  if [[ "$TS_IP" == "100.64.166.22" ]]; then
    echo "Tailscale ready: $TS_IP"
    break
  fi
  echo "Attempt $i: Tailscale not ready yet, waiting 2s..."
  sleep 2
done

if [[ "$TS_IP" != "100.64.166.22" ]]; then
  echo "ERROR: Tailscale never came up" >&2
  exit 1
fi

echo "Waiting for Ollama..."
~/jarvis/scripts/wait_for_service.sh process com.jarvis.ollama 30 || exit 1
curl -s http://localhost:11434/api/tags > /dev/null 2>&1 || sleep 5

"$HOME/jarvis/bin/mount_docs.sh" 2>/dev/null || true

TOKEN="$(security find-generic-password -a token -s jarvis.gateway.v1 -w 2>/dev/null || true)"
if [[ -z "${TOKEN}" ]]; then
  echo "Keychain locked, falling back to .secrets"
  TOKEN="$(grep '^GATEWAY_TOKEN=' /Users/jarvisbrain/jarvis/.secrets | cut -d= -f2 || true)"
fi
if [[ -z "${TOKEN}" ]]; then
  echo "ERROR: No gateway token found" >&2
  exit 2
fi
export JARVIS_GATEWAY_TOKEN="$TOKEN"
export JARVIS_GATEWAY_BASE="http://100.112.63.25:8282"

cd /Users/jarvisbrain/jarvis/services/brain
exec /Users/jarvisbrain/jarvis/services/brain/.venv/bin/uvicorn brain.app:app \
  --host 0.0.0.0 \
  --port 8182
