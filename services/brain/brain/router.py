import httpx
import json

OLLAMA_URL = "http://localhost:11434"

CODE_KEYWORDS = {
    "code", "write", "fix", "debug", "function", "script",
    "refactor", "implement", "class", "def", "import",
    "python", "javascript", "bash", "sql", "dockerfile", "regex"
}

WEB_KEYWORDS = {
    "weather", "news", "today", "current", "latest", "now",
    "search", "who is", "what is", "price", "stock", "score",
    "happening", "recently", "this week", "2024", "2025", "2026"
}

def rule_route(intent: str, complexity: int) -> dict | None:
    lower = intent.lower()
    tokens = set(lower.split())

    if tokens & CODE_KEYWORDS or any(k in lower for k in CODE_KEYWORDS):
        return {"target": "qwen", "reason": "code_keyword_match"}

    if any(k in lower for k in WEB_KEYWORDS):
        return {"target": "perplexity", "reason": "web_keyword_match"}

    if complexity <= 3:
        return {"target": "llama", "reason": "low_complexity"}

    return None

async def llama_route(intent: str) -> dict:
    system_prompt = """You are a routing classifier for an AI assistant.
Given a user query, respond with ONLY a JSON object:
{"target": "perplexity" or "claude" or "llama", "reason": "one sentence"}

Rules:
- perplexity: needs live web data, current events, real-time info
- claude: needs deep reasoning, long analysis, creative writing, complex planning
- llama: can be answered from training data, simple factual, conversational

Respond with JSON only. No other text."""

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": "llama3.1:8b",
                "prompt": f"Query: {intent}",
                "system": system_prompt,
                "stream": False
            },
            timeout=30
        )

    raw = resp.json()["response"].strip()
    try:
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        return json.loads(raw)
    except Exception:
        return {"target": "llama", "reason": "parse_fallback"}

async def route(intent: str, complexity: int = 3) -> dict:
    result = rule_route(intent, complexity)
    if result:
        return result
    return await llama_route(intent)
