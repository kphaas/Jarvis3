import httpx
import subprocess
from brain.cost_logger import log_cost, is_allowed

GATEWAY_URL = "http://100.112.63.25:8282"

def get_secret(service: str, account: str) -> str:
    result = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
        capture_output=True, text=True
    )
    return result.stdout.strip()

GATEWAY_TOKEN = get_secret("jarvis.gateway.v1", "token")

async def ask_cloud(provider: str, prompt: str, model: str = None, max_tokens: int = 1024, intent: str = "") -> dict:
    allowed, reason = await is_allowed()
    if not allowed:
        return {"response": f"[BUDGET LIMIT] {reason}", "provider": f"blocked/{provider}", "usage": {}}

    payload = {"provider": provider, "prompt": prompt, "max_tokens": max_tokens}
    if model:
        payload["model"] = model

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{GATEWAY_URL}/v1/cloud/ask",
            headers={"x-jarvis-token": GATEWAY_TOKEN, "Content-Type": "application/json"},
            json=payload
        )
    data = resp.json()
    model_used = data.get("model", model or "unknown")
    await log_cost(provider, model_used, data.get("usage", {}), intent or prompt[:200])
    return data
