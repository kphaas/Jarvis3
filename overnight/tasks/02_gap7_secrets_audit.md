# Task: GAP 7 — Secrets audit

## Goal
Find any hardcoded DSN strings or API keys in service files.

## Steps
1. Search all .py files under ~/jarvis/services/ for hardcoded postgresql:// strings
2. Search for any hardcoded API key patterns (sk-, Bearer)
3. Report findings with file names and line numbers
4. Do NOT modify any files — audit only

## Pass criteria
- Full report of hardcoded secrets posted to /v1/overnight/runs
