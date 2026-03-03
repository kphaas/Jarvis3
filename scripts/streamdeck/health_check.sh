#!/bin/bash
source /Users/jarvisendpoint/jarvis/.venv/bin/activate
osascript -e 'tell app "Terminal" to do script "source ~/jarvis/.venv/bin/activate && ~/jarvis/scripts/endpoint/jhealth.sh"'
