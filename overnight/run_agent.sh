#!/bin/zsh
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

LOG="$HOME/jarvis/overnight/logs/agent_run.log"
echo "=== JARVIS Agent Run started $(date) ===" >> "$LOG"

cd ~/jarvis/overnight
/Users/infranet/jarvis/.venv/bin/python3 agent_loop.py >> "$LOG" 2>&1

echo "=== JARVIS Agent Run complete $(date) ===" >> "$LOG"
