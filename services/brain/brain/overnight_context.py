from fastapi import APIRouter
import psycopg2
import os
from datetime import datetime
from brain.secrets import get_secret

router = APIRouter()

def get_conn():
    return psycopg2.connect(f"host=localhost port=5432 dbname=jarvis user=jarvis password={get_secret("POSTGRES_PASSWORD")}")

@router.get("/v1/overnight/claude_md")
def build_claude_md():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT instructions, replace_previous, created_at FROM overnight_instructions ORDER BY created_at DESC LIMIT 10"
    )
    instructions = cur.fetchall()

    cur.execute(
        "SELECT filename, content, doc_type, uploaded_at FROM overnight_docs ORDER BY uploaded_at DESC"
    )
    docs = cur.fetchall()

    cur.execute(
        "SELECT run_date, task_name, status, summary FROM overnight_runs ORDER BY created_at DESC LIMIT 20"
    )
    runs = cur.fetchall()

    cur.execute(
        "SELECT summary, created_at FROM conversation_memory WHERE user_id = 'ken' ORDER BY created_at DESC LIMIT 10"
    )
    memory = cur.fetchall()

    cur.close()
    conn.close()

    lines = []
    lines.append("# JARVIS Overnight Context")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Tonight's Instructions")
    if instructions:
        seen = set()
        for row in instructions:
            text, replace, created_at = row
            if replace:
                if text not in seen:
                    lines.append(f"- {text}")
                    seen.add(text)
                break
            else:
                if text not in seen:
                    lines.append(f"- {text}")
                    seen.add(text)
    else:
        lines.append("- No specific instructions. Review recent runs and continue open tasks.")
    lines.append("")

    lines.append("## Architecture & Reference Documents")
    if docs:
        for doc in docs:
            filename, content, doc_type, uploaded_at = doc
            lines.append(f"### {filename} ({doc_type}) — uploaded {str(uploaded_at)[:10]}")
            lines.append(content[:3000])
            lines.append("")
    else:
        lines.append("No documents uploaded yet.")
    lines.append("")

    lines.append("## Recent Overnight Run History")
    if runs:
        for run in runs:
            run_date, task_name, status, summary = run
            icon = "✅" if status == "pass" else "❌"
            lines.append(f"{icon} [{run_date}] {task_name} — {status}")
            if summary:
                lines.append(f"   {summary[:300]}")
    else:
        lines.append("No previous runs recorded.")
    lines.append("")

    lines.append("## Recent Conversation Memory (Ken)")
    if memory:
        for row in memory:
            content, created_at = row
            lines.append(f"- [{str(created_at)[:10]}] {str(content)[:200]}")
    else:
        lines.append("No conversation memory available.")
    lines.append("")

    lines.append("## Standing Rules")
    lines.append("- Brain venv is Python 3.14 at ~/jarvis/services/brain/.venv")
    lines.append("- Delete __pycache__ before every Brain restart after any .py edit")
    lines.append("- router.py route() must return only {target, reason}")
    lines.append("- Multi-node git: always git pull origin main --rebase before pushing")
    lines.append("- Docker abandoned permanently — Homebrew native ARM binaries only")
    lines.append("- No inline comments in terminal commands")
    lines.append("- Anthropic model string: claude-haiku-4-5-20251001")
    lines.append("- Dashboard port is :4000")
    lines.append("")

    return {"claude_md": "\n".join(lines)}
