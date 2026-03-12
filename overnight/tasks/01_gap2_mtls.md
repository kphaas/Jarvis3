# Task: GAP 2 — Verify mTLS readiness between nodes

## Goal
Check if Tailscale certificates are provisioned on Brain and Gateway.
Report current status and what is needed for mTLS.

## Steps
1. Run: tailscale cert --help on Brain to check if cert provisioning is available
2. Check if any existing certs exist in ~/jarvis/certs/ or /etc/ssl/
3. Check current HTTPS status on Brain :8182
4. Report findings — do NOT make changes, just audit and report

## Pass criteria
- Report generated and posted to /v1/overnight/runs
