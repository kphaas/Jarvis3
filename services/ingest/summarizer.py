import httpx
import json
import logging
import re

log = logging.getLogger("summarizer")

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "llama3.1:8b"
TIMEOUT = 120
MIN_CONTENT_LENGTH = 100

PROMPT_TEMPLATE = """You are a news summarizer. Read the article below and respond with ONLY a JSON object — no explanation, no markdown, no extra text.

Format:
{{"summary": "3 sentence summary here", "tags": ["tag1", "tag2", "tag3"]}}

Article:
{content}

JSON response:"""


def summarize(raw_content):
    if not raw_content or len(raw_content.strip()) < MIN_CONTENT_LENGTH:
        log.warning(f"Skipping summarization: content too short ({len(raw_content) if raw_content else 0} chars)")
        return None
    prompt = PROMPT_TEMPLATE.format(content=raw_content[:3000])
    try:
        r = httpx.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "num_predict": 500,
        }, timeout=TIMEOUT)
        r.raise_for_status()
        text = r.json().get("response", "").strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON found in response: {text[:200]}")
        parsed = json.loads(match.group())
        summary = parsed.get("summary", "").strip()
        tags = parsed.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        if not summary:
            raise ValueError("Empty summary in parsed response")
        return {"summary": summary, "tags": tags}
    except Exception as e:
        log.error(f"Summarization failed: {e}")
        return None
