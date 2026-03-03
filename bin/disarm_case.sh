#!/bin/zsh
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.jarvis.brain.plist"

# Remove the JARVIS_DOCS_ALLOW key block (simple/robust approach: rewrite plist via plutil not fun;
# we'll just open in editor for now if needed.)
echo "Open $PLIST and remove JARVIS_DOCS_ALLOW (or set it empty), then run:"
echo "  launchctl unload $PLIST 2>/dev/null || true"
echo "  launchctl load   $PLIST"
echo "  launchctl kickstart -k gui/$(id -u)/com.jarvis.brain"
