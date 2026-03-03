#!/bin/zsh
set -euo pipefail

# Pull token from macOS Keychain (no secrets in files)
TOKEN="$(security find-generic-password -a token -s jarvis.gateway -w 2>/dev/null || true)"
if [[ -z "${TOKEN}" ]]; then
  echo "ERROR: jarvis.gateway token not found in Keychain (account 'token', service 'jarvis.gateway')" >&2
  exit 2
fi
export JARVIS_GATEWAY_TOKEN="$TOKEN"

# Always run from repo root
cd /Users/infranet/jarvis

# Prefer venv if it exists, otherwise fall back to system python
VENV="/Users/infranet/jarvis/.venv"
if [[ -x "${VENV}/bin/python" ]]; then
  PY="${VENV}/bin/python"
  UVICORN="${VENV}/bin/uvicorn"
else
  PY="$(command -v python3)"
  UVICORN="$(command -v uvicorn || true)"
fi

# Ensure uvicorn exists
if [[ -z "${UVICORN}" || ! -x "${UVICORN}" ]]; then
  echo "ERROR: uvicorn not found. Install into /Users/infranet/jarvis/.venv (recommended)." >&2
  exit 3
fi

# Start gateway
exec "${UVICORN}" services.gateway.app.gateway:app --host 100.112.63.25 --port 8282
