#!/bin/bash
TASK_FILE=$1
TASK_NAME=$(basename "$TASK_FILE" .md)
RESULT_FILE=~/jarvis/overnight/results/${TASK_NAME}.json
LOG_FILE=~/jarvis/overnight/logs/${TASK_NAME}.log
BRAIN=100.64.166.22

echo "=== Task: $TASK_NAME started $(date) ===" >> $LOG_FILE

START_TIME=$(date +%s)
cd ~/jarvis
gtimeout 900 claude -p "$(cat $TASK_FILE)" --max-turns 40 --output-format text --dangerously-skip-permissions >> $LOG_FILE 2>&1
EXIT_CODE=$?
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

if [ $EXIT_CODE -eq 124 ]; then
  STATUS="fail"
  SUMMARY="Task killed after 15 minutes (timeout)"
elif [ $EXIT_CODE -eq 0 ]; then
  STATUS="pass"
  SUMMARY="Task completed successfully"
else
  STATUS="fail"
  SUMMARY="Task exited with code $EXIT_CODE"
fi

if [ ! -f "$RESULT_FILE" ]; then
  echo "{\"task\":\"$TASK_NAME\",\"status\":\"$STATUS\",\"summary\":\"$SUMMARY\",\"files_changed\":[],\"errors\":[]}" > $RESULT_FILE
fi

echo "=== Task: $TASK_NAME finished $(date) status=$STATUS ===" >> $LOG_FILE
echo "$TASK_NAME:$STATUS:$(date +%Y%m%dT%H%M%S)" >> ~/jarvis/overnight/logs/run_summary.log

RUN_DATE=$(date +%Y-%m-%d)
curl -s -X POST "http://$BRAIN:8182/v1/overnight/runs" \
  -H "Content-Type: application/json" \
  -d "{\"run_date\":\"$RUN_DATE\",\"task_name\":\"$TASK_NAME\",\"status\":\"$STATUS\",\"summary\":\"$SUMMARY\",\"duration_seconds\":$DURATION}" >> $LOG_FILE 2>&1

~/jarvis/overnight/parse_cost.sh "$TASK_NAME"
