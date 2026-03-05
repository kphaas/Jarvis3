import psycopg2
import psycopg2.extras
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

DB_DSN = "host=localhost port=5432 dbname=jarvis user=jarvis password=jarvisdb"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
_model = None

TTL_DAYS = {
    "ken": 365,
    "ryleigh": 180,
    "sloane": 180,
    "guest": 0,
}

TOKEN_BUDGET = {
    "ken": 800,
    "ryleigh": 300,
    "sloane": 300,
    "guest": 0,
}

def _get_model():
    global _model
    if _model is None:
        logger.info("Loading embedding model...")
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model

def _get_conn():
    return psycopg2.connect(DB_DSN)

def _embed(text: str) -> list:
    model = _get_model()
    return model.encode(text).tolist()

def store_memory(user_id: str, summary: str, memory_type: str = "episodic",
                 structured_data: Optional[dict] = None) -> Optional[str]:
    if user_id == "guest":
        return None
    try:
        embedding = _embed(summary)
        ttl_days = TTL_DAYS.get(user_id, 365)
        expires_at = None
        if ttl_days > 0:
            expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO conversation_memory
                        (user_id, summary, structured_data, embedding,
                         embedding_model, memory_type, expires_at)
                    VALUES (%s, %s, %s, %s::vector, %s, %s, %s)
                    RETURNING id
                """, (
                    user_id,
                    summary,
                    json.dumps(structured_data) if structured_data else None,
                    embedding,
                    EMBEDDING_MODEL,
                    memory_type,
                    expires_at,
                ))
                memory_id = str(cur.fetchone()[0])

                cur.execute("""
                    INSERT INTO memory_audit_log
                        (user_id, memory_id, action, triggered_by)
                    VALUES (%s, %s, 'write', 'system')
                """, (user_id, memory_id))

        return memory_id
    except Exception as e:
        logger.error(f"store_memory error: {e}")
        return None

def recall_memories(user_id: str, query: str, top_n: int = 5) -> list:
    if user_id == "guest" or TOKEN_BUDGET.get(user_id, 0) == 0:
        return []
    try:
        query_embedding = _embed(query)
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT id, summary, structured_data, memory_type,
                           1 - (embedding <=> %s::vector) AS similarity
                    FROM conversation_memory
                    WHERE user_id = %s
                      AND (expires_at IS NULL OR expires_at > NOW())
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, (query_embedding, user_id, query_embedding, top_n))
                rows = cur.fetchall()

                ids = [str(r["id"]) for r in rows]
                if ids:
                    cur.execute("""
                        UPDATE conversation_memory
                        SET access_count = access_count + 1,
                            last_accessed = NOW()
                        WHERE id = ANY(%s::uuid[])
                    """, (ids,))
                    for mid in ids:
                        cur.execute("""
                            INSERT INTO memory_audit_log
                                (user_id, memory_id, action, triggered_by)
                            VALUES (%s, %s, 'read', 'system')
                        """, (user_id, mid))

                return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"recall_memories error: {e}")
        return []

def build_memory_prefix(user_id: str, query: str) -> str:
    memories = recall_memories(user_id, query)
    if not memories:
        return ""
    lines = [
        "You are JARVIS, a personal AI assistant. The following are verified facts about the user from memory. You MUST use these facts in your response:\n"
    ]
    token_count = 0
    budget = TOKEN_BUDGET.get(user_id, 800)
    for m in memories:
        text = m.get("summary") or json.dumps(m.get("structured_data", {}))
        estimated_tokens = len(text.split()) * 1.3
        if token_count + estimated_tokens > budget:
            break
        lines.append(f"FACT: {text}")
        token_count += estimated_tokens
    lines.append("\nUsing the above facts, answer the following question:\n")
    return "\n".join(lines)

def delete_memory(memory_id: str, user_id: str) -> bool:
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM conversation_memory
                    WHERE id = %s AND user_id = %s
                    RETURNING id
                """, (memory_id, user_id))
                deleted = cur.fetchone()
                if deleted:
                    cur.execute("""
                        INSERT INTO memory_audit_log
                            (user_id, memory_id, action, triggered_by)
                        VALUES (%s, %s, 'delete', 'admin')
                    """, (user_id, memory_id))
                return deleted is not None
    except Exception as e:
        logger.error(f"delete_memory error: {e}")
        return False

def list_memories(user_id: str) -> list:
    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT id, summary, memory_type, access_count,
                           created_at, last_accessed, expires_at, promoted
                    FROM conversation_memory
                    WHERE user_id = %s
                    ORDER BY last_accessed DESC
                """, (user_id,))
                return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"list_memories error: {e}")
        return []

def queue_summarize_job(user_id: str, conversation: str):
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO memory_jobs (job_type, payload)
                    VALUES ('summarize', %s)
                """, (json.dumps({"user_id": user_id, "conversation": conversation}),))
    except Exception as e:
        logger.error(f"queue_summarize_job error: {e}")
