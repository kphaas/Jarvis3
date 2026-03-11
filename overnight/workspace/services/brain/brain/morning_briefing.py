"""
morning_briefing.py — GET /v1/briefing
Returns a daily briefing: recent summaries, yesterday's budget spend,
and routing decision stats.
"""

import logging
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

router = APIRouter()

DB_DSN = "host=localhost port=5432 dbname=jarvis user=jarvis password=jarvisdb"


def _get_conn():
    return psycopg2.connect(DB_DSN)


def _query_recent_summaries() -> List[Dict[str, Any]]:
    """Top 10 processed_summaries from last 24 hours, newest first."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, source, summary, created_at
                FROM processed_summaries
                WHERE created_at >= %s
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (cutoff,),
            )
            rows = cur.fetchall()
    result = []
    for row in rows:
        r = dict(row)
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
        result.append(r)
    return result


def _query_budget_yesterday() -> Dict[str, Any]:
    """Total spend from budget_events for yesterday (UTC)."""
    now = datetime.now(timezone.utc)
    yesterday_start = (now - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    yesterday_end = yesterday_start + timedelta(days=1)

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total_spend,
                       COUNT(*) AS event_count
                FROM budget_events
                WHERE created_at >= %s AND created_at < %s
                """,
                (yesterday_start, yesterday_end),
            )
            row = cur.fetchone()

    total_spend = float(row[0]) if row else 0.0
    event_count = int(row[1]) if row else 0
    return {
        "date": yesterday_start.date().isoformat(),
        "total_spend_usd": round(total_spend, 6),
        "event_count": event_count,
    }


def _query_routing_yesterday() -> Dict[str, Any]:
    """Count and most-used provider from routing_decisions for yesterday."""
    now = datetime.now(timezone.utc)
    yesterday_start = (now - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    yesterday_end = yesterday_start + timedelta(days=1)

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM routing_decisions
                WHERE created_at >= %s AND created_at < %s
                """,
                (yesterday_start, yesterday_end),
            )
            total_row = cur.fetchone()
            total_count = int(total_row[0]) if total_row else 0

            cur.execute(
                """
                SELECT provider, COUNT(*) AS cnt
                FROM routing_decisions
                WHERE created_at >= %s AND created_at < %s
                GROUP BY provider
                ORDER BY cnt DESC
                LIMIT 1
                """,
                (yesterday_start, yesterday_end),
            )
            provider_row = cur.fetchone()

    top_provider = provider_row[0] if provider_row else None
    top_provider_count = int(provider_row[1]) if provider_row else 0

    return {
        "date": yesterday_start.date().isoformat(),
        "total_decisions": total_count,
        "top_provider": top_provider,
        "top_provider_count": top_provider_count,
    }


@router.get("/v1/briefing")
async def morning_briefing() -> Dict[str, Any]:
    """Return a morning briefing: recent summaries, budget, and routing stats."""
    errors: List[str] = []

    summaries: List[Dict[str, Any]] = []
    try:
        summaries = _query_recent_summaries()
    except Exception as exc:
        logger.error("morning_briefing: summaries query failed: %s", exc)
        errors.append(f"summaries: {exc}")

    budget: Dict[str, Any] = {}
    try:
        budget = _query_budget_yesterday()
    except Exception as exc:
        logger.error("morning_briefing: budget query failed: %s", exc)
        errors.append(f"budget: {exc}")

    routing: Dict[str, Any] = {}
    try:
        routing = _query_routing_yesterday()
    except Exception as exc:
        logger.error("morning_briefing: routing query failed: %s", exc)
        errors.append(f"routing: {exc}")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summaries": summaries,
        "budget_yesterday": budget,
        "routing_yesterday": routing,
        "errors": errors if errors else None,
    }
from brain.morning_briefing import router as briefing_router
app.include_router(briefing_router)
