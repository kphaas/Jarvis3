import asyncpg
import asyncio

DB_DSN = "postgresql://jarvis:jarvisdb@localhost:5432/jarvis"

COST_PER_TOKEN = {
    "claude/claude-haiku-4-5-20251001": {"in": 0.000001, "out": 0.000005},
    "claude/claude-sonnet-4-5-20251001": {"in": 0.000003, "out": 0.000015},
    "perplexity/sonar": {"in": 0.000001, "out": 0.000001},
}

async def log_cost(provider: str, model: str, usage: dict, intent: str = ""):
    key = f"{provider}/{model}"
    rates = COST_PER_TOKEN.get(key, {"in": 0.000001, "out": 0.000001})
    prompt_t = usage.get("input_tokens", usage.get("prompt_tokens", 0))
    completion_t = usage.get("output_tokens", usage.get("completion_tokens", 0))
    cost = (prompt_t * rates["in"]) + (completion_t * rates["out"])

    conn = await asyncpg.connect(DB_DSN)
    await conn.execute(
        "INSERT INTO cloud_costs (provider, model, prompt_tokens, completion_tokens, total_tokens, cost_usd, intent) VALUES ($1,$2,$3,$4,$5,$6,$7)",
        provider, model, prompt_t, completion_t, prompt_t + completion_t, cost, intent[:500]
    )
    await conn.close()
    return cost
