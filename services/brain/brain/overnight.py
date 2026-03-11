from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import psycopg2
import os
from datetime import date

router = APIRouter()

def get_conn():
    return psycopg2.connect("host=localhost port=5432 dbname=jarvis user=jarvis password=jarvisdb")

class InstructionRequest(BaseModel):
    instructions: str
    replace_previous: bool

class DocRequest(BaseModel):
    filename: str
    content: str
    doc_type: str

class RunResult(BaseModel):
    run_date: str
    task_name: str
    status: str
    summary: Optional[str] = None
    duration_seconds: Optional[int] = None

@router.post("/v1/overnight/instructions")
def save_instructions(req: InstructionRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO overnight_instructions (instructions, replace_previous) VALUES (%s, %s)",
        (req.instructions, req.replace_previous)
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "saved"}

@router.get("/v1/overnight/instructions")
def get_instructions():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, instructions, replace_previous, created_at FROM overnight_instructions ORDER BY created_at DESC LIMIT 20"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "instructions": r[1], "replace_previous": r[2], "created_at": str(r[3])} for r in rows]

@router.delete("/v1/overnight/instructions/{instruction_id}")
def delete_instruction(instruction_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM overnight_instructions WHERE id = %s", (instruction_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "deleted"}

@router.post("/v1/overnight/docs")
def save_doc(req: DocRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO overnight_docs (filename, content, doc_type) VALUES (%s, %s, %s)",
        (req.filename, req.content, req.doc_type)
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "saved"}

@router.get("/v1/overnight/docs")
def get_docs():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, filename, doc_type, uploaded_at FROM overnight_docs ORDER BY uploaded_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "filename": r[1], "doc_type": r[2], "uploaded_at": str(r[3])} for r in rows]

@router.delete("/v1/overnight/docs/{doc_id}")
def delete_doc(doc_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM overnight_docs WHERE id = %s", (doc_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "deleted"}

@router.post("/v1/overnight/runs")
def save_run(req: RunResult):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO overnight_runs (run_date, task_name, status, summary, duration_seconds) VALUES (%s, %s, %s, %s, %s)",
        (req.run_date, req.task_name, req.status, req.summary, req.duration_seconds)
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "saved"}

@router.get("/v1/overnight/runs")
def get_runs():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, run_date, task_name, status, summary, duration_seconds, created_at FROM overnight_runs ORDER BY created_at DESC LIMIT 50"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "run_date": str(r[1]), "task_name": r[2], "status": r[3], "summary": r[4], "duration_seconds": r[5], "created_at": str(r[6])} for r in rows]

@router.get("/v1/overnight/context")
def get_context():
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

    cur.close()
    conn.close()

    return {
        "instructions": [{"text": r[0], "replace": r[1], "created_at": str(r[2])} for r in instructions],
        "docs": [{"filename": r[0], "content": r[1], "doc_type": r[2], "uploaded_at": str(r[3])} for r in docs],
        "recent_runs": [{"run_date": str(r[0]), "task": r[1], "status": r[2], "summary": r[3]} for r in runs]
    }
