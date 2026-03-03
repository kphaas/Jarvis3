import json
import re
from typing import Any, Dict, Tuple, List

from openai import OpenAI

OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
OLLAMA_MODEL = "llama3.1:8b"
CLIENT = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")

PLANNER_SYSTEM = """You are Jarvis Brain Planner.
Return ONLY valid JSON. No markdown. No extra text.

Output schema:
{
  "risk_tier": 0|1|2|3,
  "intent_type": "QNA"|"HOME"|"GATEWAY_FETCH"|"OTHER",
  "plan": [
    {
      "type": "NOOP"|"HOME_ASSISTANT_CALL"|"GATEWAY_FETCH",
      "action": "string or null",
      "parameters": { },
      "risk_tier": 0|1|2|3
    }
  ],
  "user_facing_reason": "short string"
}

Risk rules:
- buy/order/checkout/payment -> risk_tier 3 and plan should be NOOP.
- unlock/disarm/arm/alarm/security -> risk_tier 2.
- lights/thermostat/scenes -> risk_tier 1.
- information-only request -> risk_tier 0 and NOOP.
Be conservative.
"""

def _extract_json(text: str) -> Dict[str, Any]:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON found in model output: {text[:200]}")
    return json.loads(m.group(0))

def propose_plan(user_text: str, mode: str, trust_cap: int, context: Dict[str, Any]) -> Dict[str, Any]:
    resp = CLIENT.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": f"MODE={mode} TRUST_CAP={trust_cap}\nUSER_TEXT={user_text}\nCONTEXT={json.dumps(context, ensure_ascii=False)}"},
        ],
        temperature=0.1,
    )
    return _extract_json(resp.choices[0].message.content.strip())

def enforce_policy(plan_obj: Dict[str, Any], mode: str, cap: int) -> Tuple[str, str, List[Dict[str, Any]]]:
    if mode == "PRIVATE":
        return ("DENY", "PRIVATE mode: actions disabled.", [{"step_id":"1","type":"NOOP","risk_tier":0}])

    steps = plan_obj.get("plan") or []

    def _risk(st: Dict[str, Any]) -> int:
        try:
            return int(st.get("risk_tier", 0))
        except Exception:
            return 0

    max_risk = max([int(plan_obj.get("risk_tier", 0))] + [_risk(s) for s in steps])

    if max_risk > cap:
        if max_risk <= 2:
            return ("REQUIRES_APPROVAL", f"Action requires approval: risk_tier={max_risk} > trust_cap={cap}.", [{"step_id":"1","type":"NOOP","risk_tier":max_risk}])
        return ("DENY", f"Denied: risk_tier={max_risk} > trust_cap={cap}.", [{"step_id":"1","type":"NOOP","risk_tier":max_risk}])

    out: List[Dict[str, Any]] = []
    for i, st in enumerate(steps, start=1):
        t = st.get("type", "NOOP")
        out.append({
            "step_id": str(i),
            "type": t,
            "target": "executor.local" if t == "HOME_ASSISTANT_CALL" else ("gateway.local" if t == "GATEWAY_FETCH" else None),
            "action": st.get("action"),
            "parameters": st.get("parameters") or {},
            "risk_tier": _risk(st),
        })

    reason = plan_obj.get("user_facing_reason", "Allowed.")
    return ("ALLOW", reason, out)
