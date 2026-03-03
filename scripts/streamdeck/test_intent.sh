#!/bin/bash
TOKEN=$(security find-generic-password -s "jarvis.gateway.v1" -a "token" -w 2>/dev/null)
curl -s -X POST http://100.64.166.22:8182/v1/intent \
  -H "Content-Type: application/json" \
  -H "x-jarvis-token: $TOKEN" \
  -d '{
    "request_id": "sd-test-001",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "source": {"node": "endpoint", "user": "jarvisendpoint", "session_id": "streamdeck"},
    "mode": "safe",
    "trust_cap": 3,
    "input": {"type": "text", "text": "run a health check"},
    "context": {
      "presence": {"kids_present": false, "people_count": 1},
      "location": "office",
      "device_state_snapshot": {}
    }
  }' | python3 -m json.tool
