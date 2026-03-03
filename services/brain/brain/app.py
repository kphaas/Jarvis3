from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import os
import subprocess

from planner import propose_plan, enforce_policy

app = FastAPI(title="Jarvis Brain")

# -----------------------------
# Models
# -----------------------------

class Presence(BaseModel):
    kids_present: bool
    people_count: int

class Context(BaseModel):
    presence: Presence
    location: str
    device_state_snapshot: Dict[str, Any]

class InputPayload(BaseModel):
    type: str
    text: str

class Source(BaseModel):
    node: str
    user: str
    session_id: str

class IntentRequest(BaseModel):
    request_id: str
    timestamp: str
    source: Source
    mode: str
    trust_cap: int
    input: InputPayload
    context: Context

class PlanStep(BaseModel):
    step_id: str
    type: str
    target: Optional[str] = None
    action: Optional[str] = None
    parameters: Dict[str, Any] = {}
    risk_tier: int

class IntentResponse(BaseModel):
    request_id: str
    decision: str
    reason: str
    plan: List[PlanStep]
    approval: Dict[str, Any]
    audit: Dict[str, Any]

# -----------------------------
# Routes
# -----------------------------

@app.get("/health")
def health():
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}

@app.post("/v1/intent")
def intent(req: IntentRequest):

    proposed = propose_plan(
        user_text=req.input.text,
        mode=req.mode,
        trust_cap=req.trust_cap,
        context=req.context.model_dump(),
    )

    decision, reason, plan_steps = enforce_policy(
        proposed,
        req.mode,
        req.trust_cap,
    )

    approval_required = decision == "REQUIRES_APPROVAL"

    return IntentResponse(
        request_id=req.request_id,
        decision=decision,
        reason=reason,
        plan=[PlanStep(**ps) for ps in plan_steps],
        approval={
            "required": approval_required,
            "prompt": "Confirm to proceed." if approval_required else None,
        },
        audit={
            "mode_applied": req.mode,
            "trust_cap_applied": req.trust_cap,
            "policy_version": "2026-02-27",
        },
    )
@app.get("/tools/docs/status")
def docs_status():
    return {
        "docs_blocklist": sorted(DOCS_BLOCKLIST),
        "docs_allow": sorted(DOCS_ALLOW),
    }

# ============================================================
# DOCUMENTS SECURITY SUBSYSTEM
# ============================================================

DOCS_ROOT = Path(
    os.environ.get("JARVIS_DOCS_ROOT", "/Volumes/Documents")
).expanduser().resolve()

DOCS_STAGING = DOCS_ROOT / "_staging"

# Classification model
DOCS_CLASSIFICATION = {
    "Case": "restricted",
    "Backup Data": "sensitive",
}

DOCS_DEFAULT_CLASSIFICATION = "public"

DOCS_ALLOW = {
    x.strip()
    for x in os.environ.get("JARVIS_DOCS_ALLOW", "").split(",")
    if x.strip()
}
def _get_mount_info_for_path(p: Path) -> dict:
    # Uses macOS `mount` output to detect smbfs + flags.
    try:
        out = subprocess.check_output(["mount"], text=True)
    except Exception as e:
        return {"ok": False, "error": f"mount_cmd_failed:{e.__class__.__name__}"}

    p_str = str(p)
    for line in out.splitlines():
        # line example: //user@host/share on /Volumes/Documents (smbfs, read-only, ...)
        if f" on {p_str} " in line:
            # parse flags in parentheses
            flags = ""
            if "(" in line and ")" in line:
                flags = line.split("(", 1)[1].rsplit(")", 1)[0]
            flags_list = [x.strip() for x in flags.split(",") if x.strip()]
            return {
                "ok": True,
                "mount_line": line,
                "fs": flags_list[0] if flags_list else None,
                "flags": flags_list,
                "read_only": any(f in ("read-only", "rdonly") for f in flags_list),
            }

    return {"ok": False, "error": "not_mounted"}

def _verify_mount(root: Path):
    if not root.exists():
        raise HTTPException(status_code=503, detail="Documents mount missing")

    try:
        subprocess.check_output(["mount"], text=True)
    except Exception:
        raise HTTPException(status_code=503, detail="Mount validation failed")

def _safe_join(root: Path, user_path: str) -> Path:
    target = (root / user_path.lstrip("/")).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Invalid path")
    return target

def _get_classification(path: Path) -> str:
    parts = path.relative_to(DOCS_ROOT).parts
    if not parts:
        return DOCS_DEFAULT_CLASSIFICATION

    top = parts[0]
    return DOCS_CLASSIFICATION.get(top, DOCS_DEFAULT_CLASSIFICATION)

@app.get("/tools/docs/mount")
def docs_mount():
    root = DOCS_ROOT.resolve()
    info = _get_mount_info_for_path(root)

    exists = root.exists()
    can_list = False
    sample = []
    if exists:
        try:
            sample = sorted([p.name for p in root.iterdir()])[:10]
            can_list = True
        except Exception:
            can_list = False

    return {
        "docs_root": str(root),
        "exists": exists,
        "can_list": can_list,
        "sample": sample,
        "mount": info,
    }

@app.get("/tools/docs/list")
def tools_docs_list(
    path: str = Query("/", description="Path inside Documents share")
):
    root = DOCS_ROOT
    _verify_mount(root)

    target = _safe_join(root, path)

    if not target.exists():
        raise HTTPException(status_code=404, detail="Path not found")

    classification = _get_classification(target)

    # Restricted folders require explicit allow
    if classification == "restricted":
        parts = Path(path.lstrip("/")).parts
        if not parts or parts[0] not in DOCS_ALLOW:
            raise HTTPException(status_code=403, detail="Restricted path")

    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    items = []

    for entry in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        try:
            st = entry.stat()
            items.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": st.st_size,
                "mtime": st.st_mtime,
                "classification": _get_classification(entry)
            })
        except PermissionError:
            continue

        if len(items) >= 300:
            break

    return {
        "base": "Documents",
        "requested_path": path,
        "classification": classification,
        "count": len(items),
        "items": items,
    }

@app.get("/tools/docs/read")
def tools_docs_read(
    path: str = Query(..., description="File path inside Documents share")
):
    root = DOCS_ROOT
    _verify_mount(root)

    target = _safe_join(root, path)

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    classification = _get_classification(target)

    if classification == "restricted":
        parts = Path(path.lstrip("/")).parts
        if not parts or parts[0] not in DOCS_ALLOW:
            raise HTTPException(status_code=403, detail="Restricted file")

    # Only allow safe file types
    if target.suffix.lower() not in {".txt", ".md", ".json"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    content = target.read_text(errors="ignore")

    return {
        "path": path,
        "classification": classification,
        "content_preview": content[:5000]
    }

def normalize_filename(name: str) -> str:
    import re
    name = name.strip()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9._-]", "", name)
    return name.lower()

def stage_document(temp_path: Path):
    DOCS_STAGING.mkdir(exist_ok=True)
    normalized = normalize_filename(temp_path.name)
    target = DOCS_STAGING / normalized
    temp_path.rename(target)
    return target

def _get_gateway_token_from_keychain() -> str:
    # Prefer LaunchAgent env var to avoid Keychain prompts hanging the service.
    env_token = os.environ.get("JARVIS_GATEWAY_TOKEN", "").strip()
    if env_token:
        return env_token

    import subprocess
    t = subprocess.check_output(
        ["security","find-generic-password","-a","token","-s","jarvis.gateway","-w"],
        text=True
    ).strip()
    return t

# --- Gateway integration (auto-added) ---
import httpx
from pydantic import BaseModel

GATEWAY_BASE = os.environ.get("JARVIS_GATEWAY_BASE", "http://100.112.63.25:8282").rstrip("/")

class GatewayFetchRequest(BaseModel):
    url: str
@app.post("/v1/gateway_fetch")
def gateway_fetch(req: GatewayFetchRequest):
    token = _get_gateway_token_from_keychain()
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), trust_env=False) as client:
            r = client.post(
                f"{GATEWAY_BASE}/fetch",
                json={"url": req.url},
                headers={"X-Jarvis-Token": token},
            )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Gateway unreachable: {e.__class__.__name__}")

    if r.status_code >= 400:
        try:
            return r.json()
        except Exception:
            raise HTTPException(status_code=r.status_code, detail="Gateway error (non-JSON).")

    return r.json()
