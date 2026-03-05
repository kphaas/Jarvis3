import httpx
import json
import re

ENDPOINT_OLLAMA_URL = "http://100.87.223.31:3000/v1/local/ask"

PLANNER_SYSTEM = """You are a task planner for an AI system. Break the user goal into 1-4 concrete steps.

TOOLS AVAILABLE:
- ask: Answer questions using local AI. Use for facts, explanations, analysis, summaries, math, history, science. DEFAULT for most tasks. Cost: FREE.
- weather: Get current weather for a city. Use ONLY when goal asks about weather, temperature, forecast. Cost: FREE.
- news: Get latest news headlines. Use ONLY when goal asks about news, headlines, current events. Cost: FREE.
- sports: Get sports scores and schedules. Use ONLY for UGA Bulldogs, World Cup, Olympics, soccer, college football. Cost: FREE.
- web_search: Search the web. Use ONLY when none of the above tools fit and goal needs live internet data. Cost: sometimes paid.
- code_write: Write and save code to disk. Use ONLY when goal asks to create/write a program or script. Cost: FREE.
- file_read: Read an existing file from disk. Use ONLY when goal references a specific file path. Cost: FREE.

RULES:
- Always prefer weather/news/sports over web_search when the topic matches
- Only use web_search as last resort for live data not covered by other tools
- Prefer ask for any general knowledge, history, explanations, concepts
- Keep steps to minimum — 1 step is almost always enough
- Each step must use exactly one tool

Respond ONLY with a JSON array. No explanation. No markdown. Examples:
[{"tool": "weather", "input": "Atlanta, GA"}]
[{"tool": "news", "input": "SpaceX"}]
[{"tool": "sports", "input": "UGA Bulldogs latest score"}]
[{"tool": "ask", "input": "explain quantum computing"}]"""


async def plan_task(goal: str) -> list[dict]:
    payload = {
        "prompt": goal,
        "system": PLANNER_SYSTEM,
        "model": "llama3.1:8b"
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(ENDPOINT_OLLAMA_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("response", "")

    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    bracket_start = cleaned.find("[")
    bracket_end = cleaned.rfind("]")
    if bracket_start == -1 or bracket_end == -1:
        return [{"tool": "ask", "input": goal}]

    try:
        steps = json.loads(cleaned[bracket_start:bracket_end + 1])
        valid_tools = {"ask", "web_search", "weather", "news", "sports", "code_write", "file_read"}
        result = []
        for s in steps:
            if isinstance(s, dict) and s.get("tool") in valid_tools and s.get("input"):
                result.append({"tool": s["tool"], "input": s["input"]})
        return result if result else [{"tool": "ask", "input": goal}]
    except Exception:
        return [{"tool": "ask", "input": goal}]
