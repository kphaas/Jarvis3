"""
code_writer.py — Code generation logic for JARVIS.
Uses Qwen locally first, escalates to Claude if needed.
Includes self-correction loop for lint/syntax errors.

JARVIS-GENERATED: False (human-authored foundation file)
"""
import re
import logging
import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
QWEN_MODEL = "qwen2.5-coder:7b"
CODE_BLOCK_RE = re.compile(r"```(?:python)?\n(.*?)```", re.DOTALL)
logger = logging.getLogger("jarvis.code_writer")

JARVIS_HEADER = """# JARVIS-GENERATED: True
# Intent: {intent}
# Generated: {timestamp}
# Validated: {validation_summary}
# Human review: PENDING
"""


def _extract_code(text: str) -> str:
    match = CODE_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _inject_header(code: str, intent: str, timestamp: str, validation_summary: str) -> str:
    header = JARVIS_HEADER.format(
        intent=intent,
        timestamp=timestamp,
        validation_summary=validation_summary,
    )
    return header + "\n" + code


async def _call_qwen(prompt: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                OLLAMA_URL,
                json={"model": QWEN_MODEL, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")
            code = _extract_code(raw)
            if len(code) < 20:
                return {"ok": False, "code": "", "raw": raw, "error": "Output too short"}
            return {"ok": True, "code": code, "raw": raw}
    except Exception as e:
        return {"ok": False, "code": "", "raw": "", "error": str(e)}


async def generate_with_qwen(intent: str, context: str = "") -> dict:
    prompt = f"""You are an expert Python developer.
Write clean, production-quality Python code for the following task.
Return ONLY the code in a markdown Python code block. No explanation outside the block.
Only import what you actually use.

Task: {intent}
{"Context: " + context if context else ""}
"""
    return await _call_qwen(prompt)


async def fix_with_qwen(code: str, error: str, intent: str) -> dict:
    prompt = f"""You are an expert Python developer.
The following Python code has a validation error. Fix it and return the corrected code.
Return ONLY the corrected code in a markdown Python code block. No explanation outside the block.
Only import what you actually use.

Original task: {intent}

Code with error:
```python
{code}
```

Validation error:
{error}
"""
    logger.info(f"Qwen self-correction triggered: {error[:100]}")
    return await _call_qwen(prompt)


async def generate_with_claude(intent: str, context: str, cloud_client) -> dict:
    prompt = f"""You are an expert Python developer.
Write clean, production-quality Python code for the following task.
Return ONLY the code in a markdown Python code block. No explanation outside the block.
Only import what you actually use.

Task: {intent}
{"Context: " + context if context else ""}
"""
    try:
        result = await cloud_client.ask_claude(prompt, complexity=5)
        raw = result.get("response", "")
        code = _extract_code(raw)
        if len(code) < 20:
            return {"ok": False, "code": "", "raw": raw, "error": "Claude output too short"}
        return {"ok": True, "code": code, "raw": raw, "escalated": True}
    except Exception as e:
        return {"ok": False, "code": "", "raw": "", "error": str(e)}
