import os, sys, json, time, logging, httpx, psycopg2, psycopg2.extras
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.expanduser("~/jarvis/logs/agent_worker.log")),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("agent_worker")

DB_DSN = "host=localhost port=5432 dbname=jarvis user=jarvisbrain"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
BRAIN_URL = "http://127.0.0.1:8182"
POLL_INTERVAL = 30
MAX_RETRIES = 3

LOCAL_MODEL_LOW = "llama3.1:8b"
LOCAL_MODEL_CODE = "qwen2.5-coder:7b"
CLOUD_THRESHOLD = 4

def get_db():
    return psycopg2.connect(DB_DSN, cursor_factory=psycopg2.extras.RealDictCursor)

def pick_model(task):
    if task["complexity"] >= CLOUD_THRESHOLD:
        return "cloud"
    if task["task_type"] in ("code_write", "code_review", "debug", "test_gen"):
        return LOCAL_MODEL_CODE
    return LOCAL_MODEL_LOW

def call_ollama(model, prompt):
    log.info(f"Calling Ollama model={model}")
    r = httpx.post(OLLAMA_URL, json={
        "model": model,
        "prompt": prompt,
        "stream": False
    }, timeout=300)
    r.raise_for_status()
    return r.json().get("response", "")

def call_brain_cloud(task):
    log.info("Escalating to cloud via Brain")
    payload = {
        "message": task["payload"].get("prompt", task["title"]),
        "user_id": "jarvis_agent",
        "complexity_override": task["complexity"]
    }
    r = httpx.post(f"{BRAIN_URL}/v1/ask", json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data.get("response") or data.get("content") or str(data)

def build_prompt(task):
    base = task["payload"].get("prompt") or task["title"]
    context = task["payload"].get("context", "")
    return f"""You are JARVIS, a self-hosted AI assistant. Complete this task carefully and return only the result.

TASK TYPE: {task['task_type']}
TASK: {base}
{f'CONTEXT: {context}' if context else ''}

Provide a complete, production-ready response."""

def process_task(task):
    model_target = pick_model(task)
    prompt = build_prompt(task)

    if model_target == "cloud":
        result = call_brain_cloud(task)
    else:
        result = call_ollama(model_target, prompt)

    return result, model_target

def run_worker():
    log.info("Agent worker started")
    while True:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE agent_tasks
                        SET status='running', attempted_at=now(), updated_at=now()
                        WHERE id = (
                            SELECT id FROM agent_tasks
                            WHERE status='pending'
                            ORDER BY priority DESC, created_at ASC
                            LIMIT 1
                            FOR UPDATE SKIP LOCKED
                        )
                        RETURNING *
                    """)
                    row = cur.fetchone()
                    conn.commit()

                    if not row:
                        time.sleep(POLL_INTERVAL)
                        continue

                    task = dict(row)
                    log.info(f"Processing task id={task['id']} type={task['task_type']} complexity={task['complexity']}")

                    try:
                        result, model_used = process_task(task)
                        with conn.cursor() as cur2:
                            cur2.execute("""
                                UPDATE agent_tasks
                                SET status='done', result=%s, assigned_model=%s, updated_at=now()
                                WHERE id=%s
                            """, (result, model_used, task["id"]))
                            conn.commit()
                        log.info(f"Task id={task['id']} completed via {model_used}")

                    except Exception as e:
                        log.error(f"Task id={task['id']} failed: {e}")
                        with conn.cursor() as cur2:
                            cur2.execute("""
                                UPDATE agent_tasks
                                SET status='failed', error=%s, updated_at=now()
                                WHERE id=%s
                            """, (str(e), task["id"]))
                            conn.commit()

        except Exception as e:
            log.error(f"Worker loop error: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    run_worker()
