import uuid
import asyncio
import psycopg2
import psycopg2.extras
import json
from datetime import datetime, timezone
from brain.agent_planner import plan_task
from brain.agent_tools import run_tool

DB_DSN = "host=localhost port=5432 dbname=jarvis user=jarvis password=jarvisdb"


def _db():
    return psycopg2.connect(DB_DSN)


def create_agent_task(goal: str) -> str:
    task_id = str(uuid.uuid4())
    conn = _db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO agents (task_id, goal, status) VALUES (%s, %s, 'pending')",
                    (task_id, goal)
                )
    finally:
        conn.close()
    return task_id


def get_agent_status(task_id: str) -> dict | None:
    conn = _db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM agents WHERE task_id = %s", (task_id,))
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                "SELECT * FROM agent_steps WHERE task_id = %s ORDER BY step_index",
                (task_id,)
            )
            steps = cur.fetchall()
            result = dict(row)
            result["step_details"] = [dict(s) for s in steps]
            return result
    finally:
        conn.close()


def _update_agent(task_id: str, status: str, result: str = None):
    conn = _db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE agents SET status=%s, result=%s, updated_at=%s WHERE task_id=%s",
                    (status, result, datetime.now(timezone.utc), task_id)
                )
    finally:
        conn.close()


def _upsert_step(task_id: str, idx: int, tool: str, input_text: str, output: str, status: str):
    conn = _db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agent_steps (task_id, step_index, tool, input, output, status, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (task_id, idx, tool, input_text, output, status, datetime.now(timezone.utc)))
                cur.execute("""
                    UPDATE agent_steps SET output=%s, status=%s, updated_at=%s
                    WHERE task_id=%s AND step_index=%s
                """, (output, status, datetime.now(timezone.utc), task_id, idx))
    finally:
        conn.close()


async def run_agent(task_id: str, goal: str):
    try:
        _update_agent(task_id, "planning")
        steps = await plan_task(goal)

        _update_agent(task_id, "running")
        outputs = []

        for idx, step in enumerate(steps):
            tool = step.get("tool", "ask")
            input_text = step.get("input", goal)
            _upsert_step(task_id, idx, tool, input_text, "", "running")

            try:
                output = await run_tool(tool, input_text)
                _upsert_step(task_id, idx, tool, input_text, output, "done")
                outputs.append(f"Step {idx+1} ({tool}): {output[:300]}")
            except Exception as e:
                err = f"error: {e}"
                _upsert_step(task_id, idx, tool, input_text, err, "error")
                outputs.append(f"Step {idx+1} ({tool}): {err}")

        final_result = "\n".join(outputs)
        _update_agent(task_id, "complete", final_result)

    except Exception as e:
        _update_agent(task_id, "error", str(e))
