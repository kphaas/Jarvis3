#!/usr/bin/env python3
import os
import sys
import json
import time
import httpx
from agent_tools import TOOL_DEFINITIONS, execute_tool

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
BRAIN_API = "http://100.64.166.22:8182"
SECRETS_FILE = os.path.expanduser("~/jarvis/.secrets")

def get_secret(key: str) -> str:
    for line in open(SECRETS_FILE).readlines():
        if line.startswith(key + "="):
            return line.strip().split("=", 1)[1]
    return ""

def get_instructions() -> str:
    try:
        r = httpx.get(f"{BRAIN_API}/v1/overnight/instructions", timeout=10)
        data = r.json()
        instructions = data if isinstance(data, list) else [data]
        return "\n".join(i.get("instruction", "") for i in instructions)
    except Exception as e:
        return f"No instructions available: {e}"

def get_docs() -> str:
    try:
        r = httpx.get(f"{BRAIN_API}/v1/overnight/docs", timeout=10)
        docs = r.json()
        if not docs:
            return "No reference documents uploaded."
        return "\n\n---\n\n".join(
            f"DOCUMENT: {d.get('filename','unknown')} (type={d.get('doc_type','')})\n{d.get('content','')}"
            for d in docs
        )
    except Exception as e:
        return f"Could not load docs: {e}"

def post_run_result(task_name: str, status: str, summary: str, duration: int):
    try:
        httpx.post(f"{BRAIN_API}/v1/overnight/runs", json={
            "task_name": task_name,
            "status": status,
            "summary": summary,
            "duration_seconds": duration
        }, timeout=10)
    except Exception as e:
        print(f"Failed to post run result: {e}")

def run_agent():
    api_key = get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: No ANTHROPIC_API_KEY in .secrets")
        sys.exit(1)

    instructions = get_instructions()
    docs = get_docs()

    system_prompt = f"""You are the JARVIS overnight agent — an autonomous AI engineer with full access to the JARVIS system.

JARVIS is a private AI system distributed across three nodes:
- Brain: 100.64.166.22:8182 (Mac Studio M2 Ultra, Postgres, Ollama, FastAPI)
- Gateway: 100.112.63.25:8282 (MacBook, sole internet egress)
- Endpoint: 100.87.223.31 (Mac Mini, dashboard :4000, voice :4001, avatar :4002)

You have tools to SSH into Brain and Endpoint, make HTTP requests, read/write files, and restart services.

RULES:
- Never expose secrets or API keys in commands
- Always verify changes by checking results
- Use psycopg2-style DSN: postgresql://jarvis:<password>@localhost:5432/jarvis on Brain
- Brain venv is ~/jarvis/services/brain/.venv (Python 3.14)
- Delete __pycache__ before restarting Brain
- Commit changes with git after completing tasks
- Post results to /v1/overnight/runs when done
- Call task_complete when all work is finished

TONIGHT'S INSTRUCTIONS:
{instructions}

REFERENCE DOCUMENTS:
{docs}
"""

    messages = [{"role": "user", "content": "Please begin your overnight tasks now."}]
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    start = time.time()
    max_iterations = 40
    iteration = 0

    print(f"=== JARVIS Agent Loop started ===")
    print(f"Instructions: {instructions[:200]}")

    while iteration < max_iterations:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---")

        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 4096,
            "system": system_prompt,
            "tools": TOOL_DEFINITIONS,
            "messages": messages
        }

        with httpx.Client(timeout=120) as client:
            r = client.post(ANTHROPIC_API, headers=headers, json=payload)

        if r.status_code != 200:
            print(f"API error {r.status_code}: {r.text}")
            break

        response = r.json()
        content = response.get("content", [])
        stop_reason = response.get("stop_reason")

        messages.append({"role": "assistant", "content": content})

        for block in content:
            if block.get("type") == "text":
                print(f"Claude: {block['text'][:500]}")

        if stop_reason == "end_turn":
            print("Claude finished — no more tool calls.")
            break

        if stop_reason == "tool_use":
            tool_results = []
            done = False

            for block in content:
                if block.get("type") != "tool_use":
                    continue

                tool_name = block["name"]
                tool_input = block["input"]
                tool_id = block["id"]

                print(f"Tool: {tool_name}({json.dumps(tool_input)[:200]})")
                result = execute_tool(tool_name, tool_input)
                print(f"Result: {result[:300]}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result
                })

                if tool_name == "task_complete":
                    done = True
                    duration = int(time.time() - start)
                    parsed = json.loads(result)
                    post_run_result(
                        "agentic_overnight",
                        "pass",
                        parsed.get("summary", "Completed"),
                        duration
                    )

            messages.append({"role": "user", "content": tool_results})

            if done:
                print("=== Agent signaled task_complete ===")
                break

    duration = int(time.time() - start)
    print(f"\n=== Agent loop finished in {duration}s after {iteration} iterations ===")

if __name__ == "__main__":
    run_agent()
