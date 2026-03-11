import logging
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from typing import Any, Dict

logger = logging.getLogger(__name__)
router = APIRouter()

def _get_conn():
    import os
    dsn = os.environ.get("JARVIS_DB_DSN", "host=localhost dbname=jarvis user=jarvis")
    return psycopg2.connect(dsn)

@router.get("/v1/briefing")
async def morning_briefing() -> Dict[str, Any]:
    errors = []
    summaries = []
    budget = {}
    routing = {}

    now = datetime.now(timezone.utc)
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = yesterday_start + timedelta(days=1)

    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT ps.id, ps.summary, ps.processed_at
                    FROM processed_summaries ps
                    WHERE ps.processed_at >= NOW() - INTERVAL '24 hours'
                    ORDER BY ps.processed_at DESC
                    LIMIT 10
                """)
                summaries = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        errors.append(f"summaries: {e}")

    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT COALESCE(SUM(cost_usd), 0) AS total_spend,
                           COUNT(*) AS total_calls
                    FROM cloud_costs
                    WHERE ts >= %s AND ts < %s
                """, (yesterday_start, yesterday_end))
                row = cur.fetchone()
                budget = dict(row) if row else {}
    except Exception as e:
        errors.append(f"budget: {e}")

    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT provider_chosen, COUNT(*) AS cnt
                    FROM routing_decisions
                    WHERE created_at >= %s AND created_at < %s
                    GROUP BY provider_chosen
                    ORDER BY cnt DESC
                    LIMIT 1
                """, (yesterday_start, yesterday_end))
                row = cur.fetchone()
                routing = dict(row) if row else {}
                cur.execute("""
                    SELECT COUNT(*) AS total_decisions
                    FROM routing_decisions
                    WHERE created_at >= %s AND created_at < %s
                """, (yesterday_start, yesterday_end))
                total = cur.fetchone()
                if total:
                    routing["total_decisions"] = total["total_decisions"]
    except Exception as e:
        errors.append(f"routing: {e}")

    return {
        "generated_at": now.isoformat(),
        "summaries": summaries,
        "budget_yesterday": budget,
        "routing_yesterday": routing,
        "errors": errors if errors else None,
    }
