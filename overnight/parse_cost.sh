#!/bin/bash
TASK_NAME=$1
PROJECT_DIR=~/.claude/projects/-Users-infranet

LATEST=$(ls -t $PROJECT_DIR/*.jsonl 2>/dev/null | head -1)

if [ -z "$LATEST" ]; then
  echo "no claude session logs found"
  exit 0
fi

TOKENS=$(python3 -c "
import json
input_t = 0
output_t = 0
with open('$LATEST') as f:
    for line in f:
        try:
            d = json.loads(line)
            usage = d.get('usage') or d.get('message', {}).get('usage', {})
            input_t += usage.get('input_tokens', 0)
            output_t += usage.get('output_tokens', 0)
        except:
            pass
cost = round((input_t * 0.000003) + (output_t * 0.000015), 6)
print(f'{input_t} {output_t} {cost}')
" 2>/dev/null)

INPUT_T=$(echo $TOKENS | cut -d' ' -f1)
OUTPUT_T=$(echo $TOKENS | cut -d' ' -f2)
COST=$(echo $TOKENS | cut -d' ' -f3)

[ -z "$COST" ] && COST="0.001"
[ -z "$INPUT_T" ] && INPUT_T="0"
[ -z "$OUTPUT_T" ] && OUTPUT_T="0"
TOTAL_T=$((INPUT_T + OUTPUT_T))

echo "task=$TASK_NAME input=$INPUT_T output=$OUTPUT_T cost=\$$COST"

ssh jarvisbrain@100.64.166.22 "psql -U jarvisbrain -d jarvis -c \"
INSERT INTO cloud_costs (provider, model, prompt_tokens, completion_tokens, total_tokens, cost_usd, intent)
VALUES ('claude_code', 'claude-sonnet', $INPUT_T, $OUTPUT_T, $TOTAL_T, $COST, '$TASK_NAME');
\""  && echo "logged to cloud_costs" || echo "db insert failed"
