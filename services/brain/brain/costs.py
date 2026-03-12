import asyncpg
from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter()
DB_DSN = "postgresql://jarvis:jarvisdb@localhost:5432/jarvis"

@router.get("/v1/costs")
async def get_costs():
    conn = await asyncpg.connect(DB_DSN)

    total = await conn.fetchrow("SELECT COALESCE(SUM(cost_usd),0) as total, COUNT(*) as calls FROM cloud_costs")

    today = await conn.fetchrow("""
        SELECT COALESCE(SUM(cost_usd),0) as spent, COUNT(*) as calls
        FROM cloud_costs WHERE DATE(ts) = CURRENT_DATE
    """)

    this_week = await conn.fetchrow("""
        SELECT COALESCE(SUM(cost_usd),0) as spent, COUNT(*) as calls
        FROM cloud_costs WHERE DATE_TRUNC('week', ts) = DATE_TRUNC('week', NOW())
    """)

    this_month = await conn.fetchrow("""
        SELECT COALESCE(SUM(cost_usd),0) as spent, COUNT(*) as calls
        FROM cloud_costs WHERE DATE_TRUNC('month', ts) = DATE_TRUNC('month', NOW())
    """)

    daily_avg = await conn.fetchrow("""
        SELECT COALESCE(AVG(day_total),0) as avg
        FROM (SELECT DATE(ts) as day, SUM(cost_usd) as day_total FROM cloud_costs GROUP BY DATE(ts)) t
    """)

    weekly_avg = await conn.fetchrow("""
        SELECT COALESCE(AVG(week_total),0) as avg
        FROM (SELECT DATE_TRUNC('week',ts) as wk, SUM(cost_usd) as week_total FROM cloud_costs GROUP BY DATE_TRUNC('week',ts)) t
    """)

    monthly_avg = await conn.fetchrow("""
        SELECT COALESCE(AVG(month_total),0) as avg
        FROM (SELECT DATE_TRUNC('month',ts) as mo, SUM(cost_usd) as month_total FROM cloud_costs GROUP BY DATE_TRUNC('month',ts)) t
    """)

    by_day = await conn.fetch("""
        SELECT DATE(ts) as day, provider, COUNT(*) as calls,
               SUM(total_tokens) as tokens, SUM(cost_usd) as cost_usd
        FROM cloud_costs
        GROUP BY DATE(ts), provider
        ORDER BY day DESC, provider
        LIMIT 90
    """)

    by_provider = await conn.fetch("""
        SELECT provider, COUNT(*) as calls, SUM(total_tokens) as tokens, SUM(cost_usd) as cost_usd
        FROM cloud_costs GROUP BY provider ORDER BY cost_usd DESC
    """)

    limits = await conn.fetch("SELECT period, limit_usd FROM budget_config ORDER BY period")
    await conn.close()

    limits_map = {r["period"]: float(r["limit_usd"]) for r in limits}

    daily_spent   = float(today["spent"])
    weekly_spent  = float(this_week["spent"])
    monthly_spent = float(this_month["spent"])
    all_time_spent = float(total["total"])

    credit_balance = limits_map.get("credit_balance", 0.0)
    credit_remaining = round(max(0, credit_balance - all_time_spent), 4)
    credit_pct_used = round(all_time_spent / credit_balance * 100, 1) if credit_balance > 0 else 0
    credit_pct_used  = round(all_time_spent / credit_balance * 100, 1) if credit_balance > 0 else 0

    budget = {
        "daily": {
            "limit_usd":     limits_map.get("daily", 1.00),
            "spent_usd":     round(daily_spent, 6),
            "remaining_usd": round(max(0, limits_map.get("daily", 1.00) - daily_spent), 6),
            "pct_used":      round(daily_spent / limits_map.get("daily", 1.00) * 100, 1) if limits_map.get("daily") else 0,
            "calls":         today["calls"]
        },
        "weekly": {
            "limit_usd":     limits_map.get("weekly", 5.00),
            "spent_usd":     round(weekly_spent, 6),
            "remaining_usd": round(max(0, limits_map.get("weekly", 5.00) - weekly_spent), 6),
            "pct_used":      round(weekly_spent / limits_map.get("weekly", 5.00) * 100, 1) if limits_map.get("weekly") else 0,
            "calls":         this_week["calls"]
        },
        "monthly": {
            "limit_usd":     limits_map.get("monthly", 20.00),
            "spent_usd":     round(monthly_spent, 6),
            "remaining_usd": round(max(0, limits_map.get("monthly", 20.00) - monthly_spent), 6),
            "pct_used":      round(monthly_spent / limits_map.get("monthly", 20.00) * 100, 1) if limits_map.get("monthly") else 0,
            "calls":         this_month["calls"]
        }
    }

    alerts = []
    for period, data in budget.items():
        if data["pct_used"] >= 90:
            alerts.append(f"CRITICAL: {period} budget {data['pct_used']}% used (${data['spent_usd']:.4f} of ${data['limit_usd']})")
        elif data["pct_used"] >= 75:
            alerts.append(f"WARNING: {period} budget {data['pct_used']}% used (${data['spent_usd']:.4f} of ${data['limit_usd']})")

    if credit_remaining <= 2.00:
        alerts.append(f"CRITICAL: Anthropic credit balance low — ${credit_remaining:.2f} remaining")
    elif credit_remaining <= 5.00:
        alerts.append(f"WARNING: Anthropic credit balance — ${credit_remaining:.2f} remaining")

    return {
        "alerts":  alerts,
        "budget":  budget,
        "credit": {
            "balance_usd":   round(credit_balance, 2),
            "spent_usd":     round(all_time_spent, 6),
            "remaining_usd": credit_remaining,
            "pct_used":      credit_pct_used,
            "low_balance":   credit_remaining <= 2.00
        },
        "averages": {
            "daily_avg_usd":   round(float(daily_avg["avg"]), 6),
            "weekly_avg_usd":  round(float(weekly_avg["avg"]), 6),
            "monthly_avg_usd": round(float(monthly_avg["avg"]), 6),
        },
        "totals": {
            "all_time_usd":   round(all_time_spent, 6),
            "all_time_calls": total["calls"]
        },
        "by_provider": [dict(r) for r in by_provider],
        "by_day":      [dict(r) for r in by_day]
    }

@router.post("/v1/costs/budget")
async def set_budget(period: str, limit_usd: float):
    if period not in ("daily", "weekly", "monthly"):
        return {"error": "period must be daily, weekly, or monthly"}
    conn = await asyncpg.connect(DB_DSN)
    await conn.execute(
        "INSERT INTO budget_config (period, limit_usd, updated_at) VALUES ($1,$2,NOW()) ON CONFLICT (period) DO UPDATE SET limit_usd=$2, updated_at=NOW()",
        period, limit_usd
    )
    await conn.close()
    return {"status": "ok", "period": period, "limit_usd": limit_usd}

@router.post("/v1/costs/credit")
async def set_credit(balance_usd: float):
    conn = await asyncpg.connect(DB_DSN)
    await conn.execute(
        "INSERT INTO budget_config (period, limit_usd, updated_at) VALUES ('credit_balance',$1,NOW()) ON CONFLICT (period) DO UPDATE SET limit_usd=$1, updated_at=NOW()",
        balance_usd
    )
    await conn.close()
    return {"status": "ok", "credit_balance_usd": balance_usd}
