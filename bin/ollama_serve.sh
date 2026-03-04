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

exec /opt/homebrew/bin/ollama serve
