#!/bin/zsh
set -euo pipefail
curl -sS --connect-timeout 3 --max-time 20 \
  http://100.64.166.22:8182/v1/gateway_fetch \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com"}' | jq
