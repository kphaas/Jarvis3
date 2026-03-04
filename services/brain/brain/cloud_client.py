import httpx
import keyring
from brain.cost_logger import log_cost

GATEWAY_URL = "http://100.112.63.25:8282"
GATEWAY_TOKEN = keyring.get_password("jarvis.gateway.v1", "token")

async def ask_cloud(provider: str, prompt: str, model: str = None, max_tokens: int = 1024, intent: str = "") -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{GATEWAY_URL}/v1/cloud/ask",
            headers={"x-jarvis-token": GATEWAY_TOKEN, "Content-Type": "application/json"},
            json={"provider": provider, "prompt": prompt, "model": model, "max_tokens": max_tokens}
        )
    data = resp.json()
    model_used = data.get("model", model or "unknown")
    await log_cost(provider, model_used, data.get("usage", {}), intent or prompt[:200])
    return data
