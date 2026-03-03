#!/bin/bash
TOKEN=$(security find-generic-password -s "jarvis.gateway.v1" -a "token" -w 2>/dev/null)
BRAIN="http://100.64.166.22:8182"

echo "=============================="
echo " JARVIS HEALTH CHECK"
echo " $(date)"
echo "=============================="

echo ""
echo "--- Tailscale ---"
tailscale status | head -4

echo ""
echo "--- Full System ---"
curl -s --max-time 5 -H "x-jarvis-token: $TOKEN" $BRAIN/v1/health/full | python3 -m json.tool 2>/dev/null || echo "UNREACHABLE"

echo ""
echo "=============================="
