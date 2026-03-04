import httpx
import logging
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from services.gateway.app.secrets import get_secret

logger = logging.getLogger(__name__)
router = APIRouter()

GATEWAY_TOKEN = get_secret("jarvis.gateway.v1", "token")
PERPLEXITY_KEY = get_secret("jarvis.perplexity", "apikey")
ANTHROPIC_KEY = get_secret("jarvis.anthropic", "apikey")

class CloudRequest(BaseModel):
    provider: str
    prompt: str
    model: str = None
    max_tokens: int = 1024

def verify_token(token: str):
    if token != GATEWAY_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

@router.post("/v1/cloud/ask")
async def cloud_ask(req: CloudRequest, x_jarvis_token: str = Header(...)):
    verify_token(x_jarvis_token)

    if req.provider == "perplexity":
        model = req.model or "sonar"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {PERPLEXITY_KEY}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": req.prompt}], "max_tokens": req.max_tokens}
            )
        data = resp.json()
        logger.info("Perplexity raw response: %s", data)
        if "choices" not in data:
            raise HTTPException(status_code=502, detail=f"Perplexity error: {data}")
        return {"provider": "perplexity", "model": model, "response": data["choices"][0]["message"]["content"], "usage": data.get("usage", {})}

    elif req.provider == "claude":
        model = req.model or "claude-haiku-4-5-20251001"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={"model": model, "max_tokens": req.max_tokens, "messages": [{"role": "user", "content": req.prompt}]}
            )
        data = resp.json()
        logger.info("Anthropic raw response: %s", data)
        if "content" not in data:
            raise HTTPException(status_code=502, detail=f"Anthropic error: {data}")
        return {"provider": "claude", "model": model, "response": data["content"][0]["text"], "usage": data.get("usage", {})}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")
