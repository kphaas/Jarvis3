"""
router.py — Phase 5b
Routing logic for JARVIS Brain. All decisions now flow through adaptive_router
so every decision is logged, weights are respected, and circuit breakers are checked.

Security:  No external calls made here — routing decisions only, dispatch in app.py.
Resilience: adaptive_router wraps all DB calls — if DB is down, safe defaults apply.
"""

import httpx
import json
import time

from brain.adaptive_router import (
    load_weights,
    is_circuit_open,
    log_decision,
    simulate_route,
)

OLLAMA_URL = "http://localhost:11434"

# ---------------------------------------------------------------------------
# Keyword sets — single source of truth shared with adaptive_router
# ---------------------------------------------------------------------------

CODE_KEYWORDS = {
    "code", "write", "fix", "debug", "function", "script",
    "refactor", "implement", "class", "def", "import",
    "python", "javascript", "bash", "sql", "dockerfile", "regex"
}

SCRAPE_KEYWORDS = {
    "weather", "forecast", "temperature", "rain", "sunny",
    "score", "news", "headlines", "latest", "today",
    "stocks", "market", "nasdaq", "dow", "s&p",
    "uga", "dawgs", "bulldogs", "soccer", "fifa",
    "atlanta", "alpharetta", "johns creek", "roswell",
    "college football", "cfb", "olympics", "unraid",
    "events", "things to do", "weekend"
}

SEARCH_KEYWORDS = {
    "who is", "what is", "search", "find", "lookup",
    "tell me about", "research"
}


# ---------------------------------------------------------------------------
# Rule-based routing — fast path, no LLM call needed
# Returns None if no rule matched so caller can fall through to llama_route
# ---------------------------------------------------------------------------

def rule_route(intent: str, complexity: int) -> dict | None:
    """
    Apply keyword and complexity rules to pick a target.
    Returns a routing dict or None if no rule matched.
    Does NOT check circuit breakers — that happens in route() after this.
    """
    lower  = intent.lower()
    tokens = set(lower.split())

    if tokens & CODE_KEYWORDS or any(k in lower for k in CODE_KEYWORDS):
        return {"target": "qwen", "reason": "code_keyword_match"}

    if complexity <= 2:
        return {"target": "endpoint_llama", "reason": "low_complexity — offload to Endpoint"}

    if any(k in lower for k in SCRAPE_KEYWORDS):
        return {"target": "scrape", "reason": "scrape_keyword_match"}

    if any(k in lower for k in SEARCH_KEYWORDS):
        return {"target": "perplexity", "reason": "search_keyword_match"}

    if complexity <= 3:
        return {"target": "endpoint_llama", "reason": "low_complexity — offload to Endpoint"}

    return None


# ---------------------------------------------------------------------------
# LLM-guided routing — used when rules do not match (complexity 1-2 fallback)
# Calls local Llama so this is always free with no cloud dependency
# ---------------------------------------------------------------------------

async def llama_route(intent: str) -> dict:
    """
    Ask local Llama to classify the query when keyword rules do not match.
    Falls back to llama target if the response cannot be parsed.
    """
    system_prompt = """You are a routing classifier for an AI assistant.
Given a user query, respond with ONLY a JSON object:
{"target": "perplexity" or "claude" or "llama", "reason": "one sentence"}

Rules:
- perplexity: needs live search, person lookup, obscure facts
- claude: needs deep reasoning, long analysis, creative writing, complex planning
- llama: can be answered from training data, simple factual, conversational

Respond with JSON only. No other text."""

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model":  "llama3.1:8b",
                    "prompt": f"Query: {intent}",
                    "system": system_prompt,
                    "stream": False
                },
                timeout=30
            )
        raw = resp.json()["response"].strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        return json.loads(raw)
    except Exception:
        return {"target": "llama", "reason": "parse_fallback"}


# ---------------------------------------------------------------------------
# Circuit breaker fallback — picks next available provider when primary is open
# ---------------------------------------------------------------------------

def _apply_circuit_fallback(target: str, reason: str, weights: dict) -> tuple[str, str]:
    """
    If the chosen target circuit is open, walk the provider list and
    return the first available provider. Returns original target if all open.
    """
    if not is_circuit_open(target):
        return target, reason

    fallback_order = ["endpoint_llama", "qwen", "perplexity", "claude", "scrape"]
    for provider in fallback_order:
        if provider != target and not is_circuit_open(provider):
            return provider, f"circuit_fallback from {target} — {reason}"

    return target, f"all_circuits_open — attempted fallback from {target}"


# ---------------------------------------------------------------------------
# Main route() entry point — called by app.py for every request
# Logs every decision to routing_decisions table via adaptive_router
# ---------------------------------------------------------------------------

async def route(
    intent: str,
    complexity: int = 3,
    task_id: str | None = None
) -> dict:
    """
    Determine the best routing target for this intent and complexity.

    Flow:
      1. Load current weights from DB (falls back to defaults if DB down)
      2. Apply keyword / complexity rules (fast, no LLM)
      3. For low-complexity with no rule match, ask local Llama
      4. Check circuit breaker on chosen target and fallback if needed
      5. Log the decision to DB with full reasoning and weight snapshot
      6. Return {target, reason, decision_id} to app.py

    Returns decision_id so app.py can link quality ratings later.
    """
    start_ms = int(time.time() * 1000)

    weights = load_weights()
    weights_snapshot = {
        k: v["weight"] if isinstance(v, dict) else v
        for k, v in weights.items()
    }

    if complexity >= 4:
        result = rule_route(intent, complexity)
        if result and result["target"] not in ("llama", "qwen"):
            target, reason = result["target"], result["reason"]
        else:
            target, reason = "claude", "high_complexity — routed to Claude"

    elif complexity == 3:
        result = rule_route(intent, complexity)
        if result and result["target"] not in ("llama",):
            target, reason = result["target"], result["reason"]
        else:
            target, reason = "perplexity", "medium_complexity — routed to Perplexity"

    else:
        result = rule_route(intent, complexity)
        if result:
            target, reason = result["target"], result["reason"]
        else:
            llm_result = await llama_route(intent)
            target = llm_result.get("target", "endpoint_llama")
            reason = llm_result.get("reason", "llm_classified")

    target, reason = _apply_circuit_fallback(target, reason, weights)

    latency_ms  = int(time.time() * 1000) - start_ms
    decision_id = log_decision(
        intent           = intent,
        complexity       = complexity,
        provider         = target,
        reason           = reason,
        task_id          = task_id,
        latency_ms       = latency_ms,
        success          = None,
        weights_snapshot = weights_snapshot
    )

    return {
        "target":      target,
        "reason":      reason,
        "decision_id": decision_id
    }
