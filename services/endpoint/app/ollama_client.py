"""
JARVIS Endpoint Ollama Client
Wraps local Ollama API for /v1/local/ask
"""
import httpx
import time
import logging

logger = logging.getLogger(__name__)

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:8b"
TIMEOUT = 120.0


async def ask(prompt: str, model: str = DEFAULT_MODEL, system: str = None) -> dict:
    """Send a prompt to local Ollama, return response dict."""
    start = time.time()
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(f"{OLLAMA_BASE}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            elapsed = round(time.time() - start, 2)
            return {
                "ok": True,
                "model": model,
                "response": data.get("response", ""),
                "elapsed_seconds": elapsed,
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "response_tokens": data.get("eval_count", 0),
            }
    except Exception as e:
        logger.error(f"Ollama ask failed: {e}")
        return {"ok": False, "error": str(e), "model": model}


async def list_models() -> list:
    """Return list of loaded models."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return data.get("models", [])
    except Exception as e:
        logger.error(f"Ollama list_models failed: {e}")
        return []


async def health() -> dict:
    """Check if Ollama is reachable and return model info."""
    models = await list_models()
    return {
        "ollama_running": len(models) >= 0,
        "models": [m.get("name") for m in models],
        "model_count": len(models),
    }
