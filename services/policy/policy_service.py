import os
import re
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from typing import Optional, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="JARVIS Policy Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROLE_HIERARCHY = {
    "admin":          4,
    "child_ryleigh":  2,
    "child_sloane":   2,
    "guest":          1,
    "unknown":        0,
}

ROLE_MIN_LEVEL = {
    "admin":         "admin",
    "child_ryleigh": "guest",
    "child_sloane":  "guest",
    "guest":         "guest",
    "unknown":       "guest",
}

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?previous",
    r"you\s+are\s+now\s+(a\s+)?",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+(if\s+you\s+are|a\s+)",
    r"jailbreak",
    r"dan\s+mode",
    r"developer\s+mode",
    r"override\s+(safety|guidelines|instructions)",
    r"<\s*script",
    r"prompt\s*injection",
    r"system\s*prompt\s*:",
]

CHILD_BLOCKED_TOPICS = [
    r"\bviolen(t|ce)\b",
    r"\bweapon(s)?\b",
    r"\bkill(ing)?\b",
    r"\bdrug(s)?\b",
    r"\balcohol\b",
    r"\bporn(ography)?\b",
    r"\bsex(ual)?\b",
    r"\bgambl(e|ing)\b",
    r"\bhate\s+speech\b",
    r"\bsuicid(e|al)\b",
    r"\bself.harm\b",
]


def _get_secret(key: str) -> str:
    secrets_path = os.path.expanduser("~/jarvis/.secrets")
    try:
        with open(secrets_path) as f:
            for line in f:
                if line.startswith(f"{key}="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return ""


def _get_conn():
    return psycopg2.connect(
        host="localhost", port=5432,
        dbname="jarvis", user="jarvis",
        password=_get_secret("POSTGRES_PASSWORD"),
        connect_timeout=5
    )


def _get_tool(tool_name: str) -> Optional[dict]:
    try:
        conn = _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM tool_registry WHERE tool_name = %s AND enabled = true",
            (tool_name,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


def _get_classification(level: int) -> Optional[dict]:
    try:
        conn = _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM data_classification_policy WHERE level = %s",
            (level,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


def _log_decision(tool_name: str, user_id: str, role: str,
                  classification: int, decision: str, reason: str):
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO routing_decisions
               (intent, target, reason, complexity, created_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (
                f"policy:{tool_name}:{user_id}",
                decision,
                reason,
                classification,
                datetime.now(timezone.utc)
            )
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def check_injection(text: str) -> tuple[bool, str]:
    text_lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            return True, f"Injection pattern detected: {pattern}"
    return False, ""


def check_child_safety(text: str, role: str) -> tuple[bool, str]:
    if role not in ("child_ryleigh", "child_sloane"):
        return False, ""
    text_lower = text.lower()
    for pattern in CHILD_BLOCKED_TOPICS:
        if re.search(pattern, text_lower):
            return True, f"Content blocked for child profile: {pattern}"
    return False, ""


class EnforceRequest(BaseModel):
    tool_name: str
    user_id: str
    role: str
    classification: int = 10
    payload: dict = {}
    input_text: Optional[str] = None


class ScanRequest(BaseModel):
    text: str
    role: str = "unknown"


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "policy",
        "ts": datetime.now(timezone.utc).isoformat()
    }


@app.post("/v1/policy/enforce")
def enforce(req: EnforceRequest):
    injected, inj_reason = check_injection(req.input_text or "")
    if injected:
        _log_decision(req.tool_name, req.user_id, req.role,
                      req.classification, "DENY", inj_reason)
        return {"decision": "DENY", "reason": inj_reason}

    child_blocked, child_reason = check_child_safety(
        req.input_text or "", req.role
    )
    if child_blocked:
        _log_decision(req.tool_name, req.user_id, req.role,
                      req.classification, "DENY", child_reason)
        return {"decision": "DENY", "reason": child_reason}

    tool = _get_tool(req.tool_name)
    if not tool:
        reason = f"Tool not registered or disabled: {req.tool_name}"
        _log_decision(req.tool_name, req.user_id, req.role,
                      req.classification, "DENY", reason)
        return {"decision": "DENY", "reason": reason}

    caller_level = ROLE_HIERARCHY.get(req.role, 0)
    required_level = ROLE_HIERARCHY.get(tool["min_role"], 4)
    if caller_level < required_level:
        reason = f"Role {req.role} insufficient for tool {req.tool_name} (requires {tool['min_role']})"
        _log_decision(req.tool_name, req.user_id, req.role,
                      req.classification, "DENY", reason)
        return {"decision": "DENY", "reason": reason}

    if req.classification > tool["max_classification"]:
        reason = f"Classification {req.classification} exceeds tool max {tool['max_classification']}"
        _log_decision(req.tool_name, req.user_id, req.role,
                      req.classification, "DENY", reason)
        return {"decision": "DENY", "reason": reason}

    policy = _get_classification(req.classification)
    if policy and not policy["cloud_allowed"] and req.tool_name == "http_get_whitelist":
        reason = f"Cloud access not allowed at classification {req.classification}"
        _log_decision(req.tool_name, req.user_id, req.role,
                      req.classification, "DENY", reason)
        return {"decision": "DENY", "reason": reason}

    _log_decision(req.tool_name, req.user_id, req.role,
                  req.classification, "ALLOW", "Policy check passed")
    return {
        "decision": "ALLOW",
        "reason": "Policy check passed",
        "tool": tool["tool_name"],
        "scope": tool["resource_scope"],
    }


@app.post("/v1/policy/scan")
def scan(req: ScanRequest):
    injected, inj_reason = check_injection(req.text)
    if injected:
        return {"safe": False, "reason": inj_reason, "type": "injection"}
    child_blocked, child_reason = check_child_safety(req.text, req.role)
    if child_blocked:
        return {"safe": False, "reason": child_reason, "type": "child_safety"}
    return {"safe": True, "reason": "clean"}


@app.get("/v1/policy/tools")
def list_tools():
    try:
        conn = _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM tool_registry ORDER BY tool_name")
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"tools": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/policy/classifications")
def list_classifications():
    try:
        conn = _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM data_classification_policy ORDER BY level")
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"classifications": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
