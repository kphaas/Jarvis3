import asyncpg
from brain.secrets import get_secret

DB_DSN = f"postgresql://jarvis:{get_secret("POSTGRES_PASSWORD")}@localhost:5432/jarvis"

COST_PER_TOKEN = {
    "claude/claude-haiku-4-5-20251001":   {"in": 0.000001, "out": 0.000005},
    "claude/claude-sonnet-4-5-20251001":  {"in": 0.000003, "out": 0.000015},
    "claude/claude-sonnet-4-6":           {"in": 0.000003, "out": 0.000015},
    "perplexity/sonar":                   {"in": 0.000001, "out": 0.000001},
    "perplexity/sonar-pro":               {"in": 0.000003, "out": 0.000015},
}

async def check_budget(period: str, conn) -> tuple[bool, str]:
    row = await conn.fetchrow("SELECT limit_usd FROM budget_config WHERE period=$1", period)
    if not row:
        return True, ""
    col = {"daily": "CURRENT_DATE", "weekly": "DATE_TRUNC('week', NOW())", "monthly": "DATE_TRUNC('month', NOW())"}[period]
    trunc = {"daily": "DATE(ts) = CURRENT_DATE", "weekly": "DATE_TRUNC('week',ts) = DATE_TRUNC('week',NOW())", "monthly": "DATE_TRUNC('month',ts) = DATE_TRUNC('month',NOW())"}[period]
    spent = await conn.fetchrow(f"SELECT COALESCE(SUM(cost_usd),0) as total FROM cloud_costs WHERE {trunc}")
    if float(spent["total"]) >= float(row["limit_usd"]):
        return False, f"{period} budget limit ${float(row['limit_usd']):.2f} reached (spent ${float(spent['total']):.4f})"
    return True, ""

async def log_cost(provider: str, model: str, usage: dict, intent: str = "") -> float:
    key = f"{provider}/{model}"
    rates = COST_PER_TOKEN.get(key, {"in": 0.000001, "out": 0.000001})
    prompt_t     = usage.get("input_tokens", usage.get("prompt_tokens", 0))
    completion_t = usage.get("output_tokens", usage.get("completion_tokens", 0))
    cost = (prompt_t * rates["in"]) + (completion_t * rates["out"])

    conn = await asyncpg.connect(DB_DSN)
    await conn.execute(
        "INSERT INTO cloud_costs (provider, model, prompt_tokens, completion_tokens, total_tokens, cost_usd, intent) VALUES ($1,$2,$3,$4,$5,$6,$7)",
        provider, model, prompt_t, completion_t, prompt_t + completion_t, cost, intent[:500]
    )
    await conn.close()
    return cost

async def is_allowed(estimated_cost: float = 0.01) -> tuple[bool, str]:
    conn = await asyncpg.connect(DB_DSN)
    for period in ("daily", "weekly", "monthly"):
        ok, msg = await check_budget(period, conn)
        if not ok:
            await conn.close()
            return False, msg
    await conn.close()
    return True, ""
