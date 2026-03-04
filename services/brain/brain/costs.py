import asyncpg
from fastapi import APIRouter

router = APIRouter()
DB_DSN = "postgresql://jarvis:jarvisdb@localhost:5432/jarvis"

@router.get("/v1/costs")
async def get_costs():
    conn = await asyncpg.connect(DB_DSN)
    rows = await conn.fetch("""
        SELECT
            DATE(ts) as day,
            provider,
            COUNT(*) as calls,
            SUM(total_tokens) as tokens,
            SUM(cost_usd) as cost_usd
        FROM cloud_costs
        GROUP BY DATE(ts), provider
        ORDER BY day DESC, provider
        LIMIT 90
    """)
    total = await conn.fetchrow("SELECT SUM(cost_usd) as total, COUNT(*) as calls FROM cloud_costs")
    await conn.close()
    return {
        "total_usd": float(total["total"] or 0),
        "total_calls": total["calls"],
        "by_day": [dict(r) for r in rows]
    }
