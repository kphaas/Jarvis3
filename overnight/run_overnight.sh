#!/bin/bash
BUDGET_CENTS=200
SPENT_CENTS=0
TASK_DIR=~/jarvis/overnight/tasks
SUMMARY_LOG=~/jarvis/overnight/logs/run_summary.log

echo "=== JARVIS overnight run started $(date) ===" >> $SUMMARY_LOG

for TASK_FILE in $TASK_DIR/*.md; do
  [ -f "$TASK_FILE" ] || continue

  if [ $SPENT_CENTS -ge $BUDGET_CENTS ]; then
    echo "BUDGET_CAP_HIT: skipping $TASK_FILE" >> $SUMMARY_LOG
    continue
  fi

  START_TIME=$(date +%s)
  ~/jarvis/overnight/task_runner.sh "$TASK_FILE"
  END_TIME=$(date +%s)

  ELAPSED=$((END_TIME - START_TIME))
  ESTIMATED_CENTS=$(( ELAPSED / 3 ))
  SPENT_CENTS=$((SPENT_CENTS + ESTIMATED_CENTS))

  echo "budget_used: ~${SPENT_CENTS}c of ${BUDGET_CENTS}c" >> $SUMMARY_LOG
done

echo "=== JARVIS overnight run complete $(date) total_budget_used: ~${SPENT_CENTS}c ===" >> $SUMMARY_LOG
