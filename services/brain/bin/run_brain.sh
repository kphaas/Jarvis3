#!/bin/zsh
set -euo pipefail

echo "Waiting for Tailscale..."
for i in {1..30}; do
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
for i in {1..30}; do
  if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Ollama ready"
    break
  fi
  echo "Attempt $i: Ollama not ready yet, waiting 2s..."
  sleep 2
done

"$HOME/jarvis/bin/mount_docs.sh" 2>/dev/null || true

TOKEN="$(security find-generic-password -a token -s jarvis.gateway.v1 -w)"
export JARVIS_GATEWAY_TOKEN="$TOKEN"
export JARVIS_GATEWAY_BASE="http://100.112.63.25:8282"

cd /Users/jarvisbrain/jarvis/services/brain/brain
exec /Users/jarvisbrain/jarvis/services/brain/.venv/bin/uvicorn app:app \
  --host 0.0.0.0 \
  --port 8182
