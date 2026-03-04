#!/bin/zsh
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "Waiting for Tailscale..."
for i in {1..60}; do
  TS_IP=$(tailscale ip -4 2>/dev/null || true)
  if [[ "$TS_IP" == "100.112.63.25" ]]; then
    echo "Tailscale ready: $TS_IP"
    break
  fi
  echo "Attempt $i: Tailscale not ready yet, waiting 2s..."
  sleep 2
done

if [[ "$TS_IP" != "100.112.63.25" ]]; then
  echo "ERROR: Tailscale never came up" >&2
  exit 1
fi

TOKEN="$(security find-generic-password -a token -s jarvis.gateway.v1 -w 2>/dev/null || true)"
if [[ -z "${TOKEN}" ]]; then
  echo "Keychain locked, falling back to .secrets file"
  TOKEN="$(grep '^GATEWAY_TOKEN=' /Users/infranet/jarvis/.secrets | cut -d= -f2 || true)"
fi
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
