#!/bin/bash
TASK_FILE=$1
TASK_NAME=$(basename "$TASK_FILE" .md)
RESULT_FILE=~/jarvis/overnight/results/${TASK_NAME}.json
LOG_FILE=~/jarvis/overnight/logs/${TASK_NAME}.log

echo "=== Task: $TASK_NAME started $(date) ===" >> $LOG_FILE

cd ~/jarvis
gtimeout 900 claude -p "$(cat $TASK_FILE)" --max-turns 40 --output-format text --dangerously-skip-permissions >> $LOG_FILE 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 124 ]; then
  STATUS="timeout"
  SUMMARY="Task killed after 15 minutes"
elif [ $EXIT_CODE -eq 0 ]; then
  STATUS="complete"
  SUMMARY="Task completed successfully"
else
  STATUS="error"
  SUMMARY="Task exited with code $EXIT_CODE"
fi

if [ ! -f "$RESULT_FILE" ]; then
  echo "{\"task\":\"$TASK_NAME\",\"status\":\"$STATUS\",\"summary\":\"$SUMMARY\",\"files_changed\":[],\"errors\":[]}" > $RESULT_FILE
fi

echo "=== Task: $TASK_NAME finished $(date) status=$STATUS ===" >> $LOG_FILE
echo "$TASK_NAME:$STATUS:$(date +%Y%m%dT%H%M%S)" >> ~/jarvis/overnight/logs/run_summary.log

~/jarvis/overnight/parse_cost.sh "$TASK_NAME"
