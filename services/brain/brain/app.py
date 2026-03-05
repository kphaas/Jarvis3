from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import os
import subprocess
from fastapi.middleware.cors import CORSMiddleware

from brain.planner import propose_plan, enforce_policy

app = FastAPI(title="Jarvis Brain")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4000", "http://100.87.223.31:4000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        ["security","find-generic-password","-a","token","-s","jarvis.gateway.v1","-w"],
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

# -----------------------------
# Full Health Check
# -----------------------------

@app.get("/v1/health/full")
def health_full():
    results = {}
    ts = datetime.utcnow().isoformat()

    results["brain"] = {"status": "ok", "ts": ts}

    try:
        gateway_token = subprocess.run(
            ["security", "find-generic-password", "-s", "jarvis.gateway.v1", "-a", "token", "-w"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        import requests as req
        r = req.get("http://100.112.63.25:8282/health",
                    headers={"x-jarvis-token": gateway_token},
                    timeout=5)
        results["gateway"] = r.json()
    except Exception as e:
        results["gateway"] = {"status": "error", "detail": str(e)}

    try:
        mount_path = Path(os.path.expanduser("~/jarvis_mounts/Documents"))
        results["unraid_mount"] = {
            "status": "ok" if mount_path.exists() and any(mount_path.iterdir()) else "empty",
            "path": str(mount_path)
        }
    except Exception as e:
        results["unraid_mount"] = {"status": "error", "detail": str(e)}

    try:
        staging_path = Path(os.path.expanduser("~/jarvis_staging"))
        results["staging"] = {
            "status": "ok" if staging_path.exists() else "missing",
            "path": str(staging_path)
        }
    except Exception as e:
        results["staging"] = {"status": "error", "detail": str(e)}

    try:
        log_path = Path(os.path.expanduser("~/jarvis/logs/brain.log"))
        results["logs"] = {
            "status": "ok" if log_path.exists() else "missing",
            "size_bytes": log_path.stat().st_size if log_path.exists() else 0
        }
    except Exception as e:
        results["logs"] = {"status": "error", "detail": str(e)}

    try:
        import httpx as _httpx
        r = _httpx.get("http://localhost:11434/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        llama_ok = any("llama3.1" in m for m in models)
        qwen_ok  = any("qwen2.5-coder" in m for m in models)
        results["ollama"] = {
            "status": "ok" if r.status_code == 200 else "error",
            "models": models
        }
        results["ollama_llama"] = {
            "status": "ok" if llama_ok else "missing",
            "model": "llama3.1:8b"
        }
        results["ollama_qwen"] = {
            "status": "ok" if qwen_ok else "missing",
            "model": "qwen2.5-coder:7b"
        }
    except Exception as e:
        results["ollama"]       = {"status": "error", "detail": str(e)}
        results["ollama_llama"] = {"status": "error", "detail": str(e)}
        results["ollama_qwen"]  = {"status": "error", "detail": str(e)}

    try:
        import asyncio as _asyncio
        import asyncpg as _asyncpg
        _conn = _asyncio.run(_asyncpg.connect("postgresql://jarvis:jarvisdb@localhost:5432/jarvis"))
        _today   = _asyncio.run(_conn.fetchrow("SELECT COALESCE(SUM(cost_usd),0) as spent FROM cloud_costs WHERE DATE(ts)=CURRENT_DATE"))
        _week    = _asyncio.run(_conn.fetchrow("SELECT COALESCE(SUM(cost_usd),0) as spent FROM cloud_costs WHERE DATE_TRUNC('week',ts)=DATE_TRUNC('week',NOW())"))
        _month   = _asyncio.run(_conn.fetchrow("SELECT COALESCE(SUM(cost_usd),0) as spent FROM cloud_costs WHERE DATE_TRUNC('month',ts)=DATE_TRUNC('month',NOW())"))
        _limits  = _asyncio.run(_conn.fetch("SELECT period, limit_usd FROM budget_config"))
        _asyncio.run(_conn.close())
        _lmap = {r["period"]: float(r["limit_usd"]) for r in _limits}
        _ds = float(_today["spent"]); _ws = float(_week["spent"]); _ms = float(_month["spent"])
        _alerts = []
        for _p, _s, _l in [("daily",_ds,_lmap.get("daily",1)),("weekly",_ws,_lmap.get("weekly",5)),("monthly",_ms,_lmap.get("monthly",20))]:
            _pct = _s/_l*100 if _l else 0
            if _pct >= 90: _alerts.append(f"CRITICAL: {_p} {_pct:.1f}% used")
            elif _pct >= 75: _alerts.append(f"WARNING: {_p} {_pct:.1f}% used")
        results["costs"] = {
            "status": "critical" if any("CRITICAL" in a for a in _alerts) else "warning" if _alerts else "ok",
            "alerts": _alerts,
            "today_usd":   round(_ds, 6),
            "week_usd":    round(_ws, 6),
            "month_usd":   round(_ms, 6),
            "today_limit":   _lmap.get("daily", 1.00),
            "week_limit":    _lmap.get("weekly", 5.00),
            "month_limit":   _lmap.get("monthly", 20.00),
            "today_remaining":   round(max(0, _lmap.get("daily",1) - _ds), 6),
            "week_remaining":    round(max(0, _lmap.get("weekly",5) - _ws), 6),
            "month_remaining":   round(max(0, _lmap.get("monthly",20) - _ms), 6),
        }
    except Exception as e:
        results["costs"] = {"status": "error", "detail": str(e)}

    try:
        import psycopg2
        _conn = psycopg2.connect("postgresql://jarvis:jarvisdb@localhost:5432/jarvis")
        _cur = _conn.cursor()
        _cur.execute("SELECT COALESCE(SUM(cost_usd),0) FROM cloud_costs WHERE DATE(ts)=CURRENT_DATE")
        _ds = float(_cur.fetchone()[0])
        _cur.execute("SELECT COALESCE(SUM(cost_usd),0) FROM cloud_costs WHERE DATE_TRUNC('week',ts)=DATE_TRUNC('week',NOW())")
        _ws = float(_cur.fetchone()[0])
        _cur.execute("SELECT COALESCE(SUM(cost_usd),0) FROM cloud_costs WHERE DATE_TRUNC('month',ts)=DATE_TRUNC('month',NOW())")
        _ms = float(_cur.fetchone()[0])
        _cur.execute("SELECT period, limit_usd FROM budget_config")
        _lmap = {r[0]: float(r[1]) for r in _cur.fetchall()}
        _conn.close()
        _alerts = []
        for _p, _s, _l in [("daily",_ds,_lmap.get("daily",1)),("weekly",_ws,_lmap.get("weekly",5)),("monthly",_ms,_lmap.get("monthly",20))]:
            _pct = _s/_l*100 if _l else 0
            if _pct >= 90: _alerts.append(f"CRITICAL: {_p} {_pct:.1f}% used")
            elif _pct >= 75: _alerts.append(f"WARNING: {_p} {_pct:.1f}% used")
        results["costs"] = {
            "status": "critical" if any("CRITICAL" in a for a in _alerts) else "warning" if _alerts else "ok",
            "alerts": _alerts,
            "today_usd":         round(_ds, 6),
            "week_usd":          round(_ws, 6),
            "month_usd":         round(_ms, 6),
            "today_limit":       _lmap.get("daily", 1.00),
            "week_limit":        _lmap.get("weekly", 5.00),
            "month_limit":       _lmap.get("monthly", 20.00),
            "today_remaining":   round(max(0, _lmap.get("daily",1.00) - _ds), 6),
            "week_remaining":    round(max(0, _lmap.get("weekly",5.00) - _ws), 6),
            "month_remaining":   round(max(0, _lmap.get("monthly",20.00) - _ms), 6),
        }
    except Exception as e:
        results["costs"] = {"status": "error", "detail": str(e)}

    overall = "ok" if all(v.get("status") == "ok" for v in results.values()) else "degraded"

    return {"status": overall, "ts": ts, "subsystems": results}

# -----------------------------
# Dashboard UI
# -----------------------------

from fastapi.responses import HTMLResponse

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JARVIS — System Intelligence</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #060608; --bg2: #0d0d12; --bg3: #13131a;
  --border: #1e1e2e; --border2: #2a2a3e;
  --green: #00ff88; --green2: #00cc6a;
  --yellow: #ffcc00; --red: #ff4466;
  --blue: #4488ff; --purple: #9966ff;
  --dim: #3a3a5c; --text: #c8c8e8;
  --text2: #7878a8; --text3: #4a4a6a;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--bg); color: var(--text); font-family: 'JetBrains Mono', monospace; min-height: 100vh; overflow-x: hidden; }
body::before { content: ''; position: fixed; inset: 0; background-image: linear-gradient(rgba(0,255,136,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,136,0.03) 1px, transparent 1px); background-size: 40px 40px; pointer-events: none; z-index: 0; }
.container { position: relative; z-index: 1; max-width: 1400px; margin: 0 auto; padding: 24px; }
.header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 32px; padding-bottom: 24px; border-bottom: 1px solid var(--border); }
.logo-area { display: flex; align-items: center; gap: 16px; }
.logo-icon { width: 48px; height: 48px; background: linear-gradient(135deg, #00ff88, #00aa55); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; box-shadow: 0 0 24px rgba(0,255,136,0.3); animation: pulse-glow 3s ease-in-out infinite; }
@keyframes pulse-glow { 0%,100% { box-shadow: 0 0 24px rgba(0,255,136,0.3); } 50% { box-shadow: 0 0 40px rgba(0,255,136,0.6); } }
.logo-text { font-family: 'Syne', sans-serif; font-size: 32px; font-weight: 800; color: var(--green); letter-spacing: 4px; line-height: 1; }
.logo-sub { font-size: 10px; color: var(--text3); letter-spacing: 3px; text-transform: uppercase; margin-top: 4px; }
.header-right { text-align: right; }
.overall-badge { display: inline-flex; align-items: center; gap: 8px; padding: 8px 16px; border-radius: 999px; font-size: 12px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; border: 1px solid; margin-bottom: 8px; }
.overall-badge.ok { color: var(--green); border-color: var(--green); background: rgba(0,255,136,0.08); }
.overall-badge.degraded { color: var(--yellow); border-color: var(--yellow); background: rgba(255,204,0,0.08); }
.overall-badge.error { color: var(--red); border-color: var(--red); background: rgba(255,68,102,0.08); }
.pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; animation: blink 1.5s ease-in-out infinite; }
@keyframes blink { 0%,100% { opacity:1; } 50% { opacity:0.2; } }
.ts-display { font-size: 10px; color: var(--text3); letter-spacing: 1px; }
.countdown-bar { width: 120px; height: 2px; background: var(--border); border-radius: 2px; margin-top: 6px; margin-left: auto; overflow: hidden; }
.countdown-fill { height: 100%; background: var(--green); border-radius: 2px; transition: width 1s linear; }
.alerts-banner { background: rgba(255,68,102,0.08); border: 1px solid rgba(255,68,102,0.3); border-radius: 8px; padding: 12px 16px; margin-bottom: 24px; display: none; }
.alerts-banner.active { display: block; }
.alert-item { font-size: 12px; color: var(--red); display: flex; align-items: center; gap: 8px; }
.alert-item + .alert-item { margin-top: 6px; }
.section-label { font-size: 10px; color: var(--text3); letter-spacing: 3px; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center; gap: 12px; }
.section-label::after { content: ''; flex: 1; height: 1px; background: var(--border); }
.cost-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 32px; }
.cost-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 12px; padding: 20px; position: relative; overflow: hidden; }
.cost-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: var(--green); opacity: 0.6; }
.cost-card.warning::before { background: var(--yellow); }
.cost-card.critical::before { background: var(--red); }
.cost-card.warning { border-color: rgba(255,204,0,0.3); }
.cost-card.critical { border-color: rgba(255,68,102,0.3); }
.cost-period { font-size: 10px; color: var(--text3); letter-spacing: 3px; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; }
.cost-spent { font-family: 'Syne', sans-serif; font-size: 28px; font-weight: 700; color: var(--text); line-height: 1; margin-bottom: 4px; }
.cost-spent span { font-size: 14px; color: var(--text2); font-weight: 400; }
.cost-limit { font-size: 11px; color: var(--text3); margin-bottom: 16px; }
.progress-track { height: 6px; background: var(--border); border-radius: 6px; overflow: hidden; margin-bottom: 12px; }
.progress-fill { height: 100%; border-radius: 6px; background: var(--green); transition: width 0.6s cubic-bezier(0.4,0,0.2,1); }
.progress-fill.warning { background: var(--yellow); }
.progress-fill.critical { background: var(--red); }
.cost-footer { display: flex; justify-content: space-between; font-size: 10px; color: var(--text3); }
.cost-remaining { color: var(--green); }
.cost-remaining.warning { color: var(--yellow); }
.cost-remaining.critical { color: var(--red); }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 32px; }
.stat-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
.stat-label { font-size: 9px; color: var(--text3); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px; }
.stat-value { font-family: 'Syne', sans-serif; font-size: 22px; font-weight: 700; color: var(--blue); }
.stat-value.green { color: var(--green); }
.stat-value.purple { color: var(--purple); }
.stat-value.yellow { color: var(--yellow); }
.stat-sub { font-size: 10px; color: var(--text3); margin-top: 4px; }
.provider-row { display: flex; gap: 12px; margin-bottom: 32px; }
.provider-card { flex: 1; background: var(--bg2); border: 1px solid var(--border); border-radius: 10px; padding: 16px; display: flex; align-items: center; gap: 16px; }
.provider-icon { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.provider-icon.claude { background: rgba(255,68,102,0.12); }
.provider-icon.perplexity { background: rgba(68,136,255,0.12); }
.provider-name { font-size: 11px; color: var(--text2); margin-bottom: 4px; letter-spacing: 1px; }
.provider-cost { font-family: 'Syne', sans-serif; font-size: 20px; font-weight: 700; color: var(--text); }
.provider-calls { font-size: 10px; color: var(--text3); margin-top: 2px; }
.systems-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
.sys-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 10px; padding: 16px; transition: all 0.2s; animation: fadeIn 0.4s ease both; }
@keyframes fadeIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
.sys-card:hover { border-color: var(--border2); background: var(--bg3); }
.sys-card.ok { border-left: 3px solid var(--green); }
.sys-card.error { border-left: 3px solid var(--red); }
.sys-card.degraded, .sys-card.warning { border-left: 3px solid var(--yellow); }
.sys-card.missing { border-left: 3px solid var(--dim); }
.sys-icon { font-size: 20px; margin-bottom: 10px; display: block; }
.sys-name { font-size: 9px; color: var(--text3); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 6px; }
.sys-status { font-size: 13px; font-weight: 600; letter-spacing: 1px; }
.sys-status.ok { color: var(--green); }
.sys-status.error { color: var(--red); }
.sys-status.degraded, .sys-status.warning { color: var(--yellow); }
.sys-status.missing { color: var(--dim); }
.sys-detail { font-size: 10px; color: var(--text3); margin-top: 6px; word-break: break-all; line-height: 1.5; }
.sys-models { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
.model-tag { font-size: 9px; padding: 2px 8px; background: rgba(0,255,136,0.08); border: 1px solid rgba(0,255,136,0.2); border-radius: 999px; color: var(--green2); }
.footer { display: flex; justify-content: space-between; align-items: center; padding-top: 20px; border-top: 1px solid var(--border); font-size: 10px; color: var(--text3); letter-spacing: 1px; }
.footer-nodes { display: flex; gap: 20px; }
.node-tag { display: flex; align-items: center; gap: 6px; }
.node-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); }
.budget-btn { font-size: 9px; color: var(--text3); letter-spacing: 1px; cursor: pointer; background: none; border: 1px solid var(--border); border-radius: 4px; padding: 3px 8px; font-family: inherit; transition: all 0.2s; }
.budget-btn:hover { border-color: var(--green); color: var(--green); }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo-area">
      <div class="logo-icon">&#9889;</div>
      <div>
        <div class="logo-text">JARVIS</div>
        <div class="logo-sub">Private AI Infrastructure</div>
      </div>
    </div>
    <div class="header-right">
      <div id="overall-badge" class="overall-badge ok"><div class="pulse-dot"></div><span id="overall-text">LOADING</span></div>
      <div id="ts-display" class="ts-display">-</div>
      <div class="countdown-bar"><div id="countdown-fill" class="countdown-fill" style="width:100%"></div></div>
    </div>
  </div>
  <div id="alerts-banner" class="alerts-banner"><div id="alerts-list"></div></div>
  <div class="section-label">&#128176; Budget Tracker</div>
  <div class="cost-grid">
    <div id="cost-daily" class="cost-card"><div class="cost-period"><span>Daily</span><span>&#128197;</span></div><div class="cost-spent">Loading...</div></div>
    <div id="cost-weekly" class="cost-card"><div class="cost-period"><span>Weekly</span><span>&#128198;</span></div><div class="cost-spent">Loading...</div></div>
    <div id="cost-monthly" class="cost-card"><div class="cost-period"><span>Monthly</span><span>&#128467;</span></div><div class="cost-spent">Loading...</div></div>
  </div>
  <div class="section-label">&#128202; Spend Analytics</div>
  <div class="stats-row">
    <div class="stat-card"><div class="stat-label">Daily Avg</div><div id="avg-daily" class="stat-value green">-</div><div class="stat-sub">per active day</div></div>
    <div class="stat-card"><div class="stat-label">Weekly Avg</div><div id="avg-weekly" class="stat-value">-</div><div class="stat-sub">per week</div></div>
    <div class="stat-card"><div class="stat-label">Monthly Avg</div><div id="avg-monthly" class="stat-value purple">-</div><div class="stat-sub">per month</div></div>
    <div class="stat-card"><div class="stat-label">All Time</div><div id="total-cost" class="stat-value yellow">-</div><div id="total-calls" class="stat-sub">- calls</div></div>
  </div>
  <div class="section-label">&#128268; Provider Breakdown</div>
  <div id="provider-row" class="provider-row"></div>
  <div class="section-label">&#128187; System Health</div>
  <div id="systems-grid" class="systems-grid"></div>
  <div class="footer">
    <div class="footer-nodes">
      <div class="node-tag"><div class="node-dot"></div>Brain 100.64.166.22:8182</div>
      <div class="node-tag"><div class="node-dot"></div>Gateway 100.112.63.25:8282</div>
      <div class="node-tag"><div class="node-dot"></div>Endpoint 100.87.223.31:3000</div>
    </div>
    <div>auto-refresh 15s &middot; <span id="countdown-text">15</span>s</div>
  </div>
</div>
<script>
const ICONS={brain:"&#129504;",gateway:"&#127760;",unraid_mount:"&#128190;",staging:"&#128193;",logs:"&#128203;",ollama:"&#129302;",ollama_llama:"&#129466;",ollama_qwen:"&#128187;",costs:"&#128176;"};
function fmtS(u){return u===undefined||u===null?"$0.0000":"$"+Number(u).toFixed(4);}
function pctCls(p){return p>=90?"critical":p>=75?"warning":"";}
function renderCostCard(id,period,icon,data){
  const card=document.getElementById("cost-"+id);
  if(!data)return;
  const pct=data.pct_used||0,cls=pctCls(pct);
  card.className="cost-card "+cls;
  card.innerHTML=`<div class="cost-period"><span>${period}</span><div style="display:flex;gap:8px;align-items:center"><button class="budget-btn" onclick="setBudget('${id}')">edit limit</button><span>${icon}</span></div></div><div class="cost-spent">$${Number(data.spent_usd).toFixed(4)}<span> / $${Number(data.limit_usd).toFixed(2)}</span></div><div class="cost-limit">${pct.toFixed(1)}% used &middot; ${data.calls} calls</div><div class="progress-track"><div class="progress-fill ${cls}" style="width:${Math.min(pct,100)}%"></div></div><div class="cost-footer"><span>Remaining</span><span class="cost-remaining ${cls}">$${Number(data.remaining_usd).toFixed(4)}</span></div>`;
}
function renderProviders(ps){
  const row=document.getElementById("provider-row");
  if(!ps||!ps.length){row.innerHTML='<div style="color:var(--text3);font-size:12px">No cloud calls yet</div>';return;}
  const pi={claude:"&#129302;",perplexity:"&#128269;"};
  row.innerHTML=ps.map(p=>`<div class="provider-card"><div class="provider-icon ${p.provider}">${pi[p.provider]||"&#9889;"}</div><div><div class="provider-name">${p.provider.toUpperCase()}</div><div class="provider-cost">$${Number(p.cost_usd).toFixed(4)}</div><div class="provider-calls">${p.calls} calls &middot; ${p.tokens||0} tokens</div></div></div>`).join("");
}
function renderSystems(sub){
  const grid=document.getElementById("systems-grid");
  const skip=["costs"];
  const entries=Object.entries(sub).filter(([k])=>!skip.includes(k));
  grid.innerHTML=entries.map(([key,val],i)=>{
    const st=val.status||"error",icon=ICONS[key]||"&#128295;";
    let detail="";
    if(val.path)detail=val.path.split("/").pop();
    else if(val.detail)detail=val.detail.substring(0,60);
    else if(val.size_bytes!==undefined)detail=(val.size_bytes/1024).toFixed(1)+" KB";
    let models="";
    if(val.models)models=`<div class="sys-models">${val.models.map(m=>`<span class="model-tag">${m.split(":")[0]}</span>`).join("")}</div>`;
    else if(val.model)models=`<div class="sys-models"><span class="model-tag">${val.model.split(":")[0]}</span></div>`;
    return `<div class="sys-card ${st}" style="animation-delay:${i*0.05}s"><span class="sys-icon">${icon}</span><div class="sys-name">${key.replace(/_/g," ")}</div><div class="sys-status ${st}">${st.toUpperCase()}</div>${detail?`<div class="sys-detail">${detail}</div>`:""}${models}</div>`;
  }).join("");
}
async function fetchAll(){
  try{
    const[hRes,cRes]=await Promise.all([fetch("/v1/health/full"),fetch("/v1/costs")]);
    const health=await hRes.json(),costs=await cRes.json();
    const badge=document.getElementById("overall-badge");
    badge.className="overall-badge "+health.status;
    document.getElementById("overall-text").textContent=health.status.toUpperCase();
    document.getElementById("ts-display").textContent=new Date(health.ts).toLocaleTimeString();
    const alerts=costs.alerts||[];
    const banner=document.getElementById("alerts-banner");
    if(alerts.length){banner.classList.add("active");document.getElementById("alerts-list").innerHTML=alerts.map(a=>`<div class="alert-item">&#9888; ${a}</div>`).join("");}
    else banner.classList.remove("active");
    renderCostCard("daily","Daily","&#128197;",costs.budget?.daily);
    renderCostCard("weekly","Weekly","&#128198;",costs.budget?.weekly);
    renderCostCard("monthly","Monthly","&#128467;",costs.budget?.monthly);
    const avg=costs.averages||{};
    document.getElementById("avg-daily").textContent=fmtS(avg.daily_avg_usd);
    document.getElementById("avg-weekly").textContent=fmtS(avg.weekly_avg_usd);
    document.getElementById("avg-monthly").textContent=fmtS(avg.monthly_avg_usd);
    document.getElementById("total-cost").textContent=fmtS(costs.totals?.all_time_usd);
    document.getElementById("total-calls").textContent=(costs.totals?.all_time_calls||0)+" calls total";
    renderProviders(costs.by_provider);
    renderSystems(health.subsystems);
  }catch(e){
    document.getElementById("overall-text").textContent="UNREACHABLE";
    document.getElementById("overall-badge").className="overall-badge error";
  }
}
async function setBudget(period){
  const val=prompt("Set "+period+" budget limit (USD):");
  if(!val||isNaN(val))return;
  try{const res=await fetch("/v1/costs/budget?period="+period+"&limit_usd="+parseFloat(val),{method:"POST"});const d=await res.json();if(d.status==="ok")fetchAll();}catch(e){alert("Failed");}
}
fetchAll();
let sec=15;
setInterval(()=>{sec--;document.getElementById("countdown-text").textContent=sec;document.getElementById("countdown-fill").style.width=(sec/15*100)+"%";if(sec<=0){sec=15;fetchAll();}},1000);
</script>
</body>
</html>
"""


from brain.router import route

class AskRequest(BaseModel):
    intent: str
    complexity: int = 3

@app.post("/v1/ask")
async def ask(req: AskRequest):
    routing = await route(req.intent, req.complexity)
    target  = routing["target"]

    if target == "qwen":
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": "qwen2.5-coder:7b", "prompt": req.intent, "stream": False},
                timeout=60
            )
        text     = r.json()["response"]
        provider = "local/qwen"

    elif target == "llama":
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama3.1:8b", "prompt": req.intent, "stream": False},
                timeout=60
            )
        text     = r.json()["response"]
        provider = "local/llama"


    elif target == "endpoint_llama":
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "http://100.87.223.31:3000/v1/local/ask",
                json={"model": "llama3.1:8b", "prompt": req.intent},
                timeout=90
            )
        data     = r.json()
        text     = data.get("response", "No response from Endpoint")
        provider = "local/endpoint_llama"

    elif target == "scrape":
        scrape_target = find_scrape_target(req.intent)
        if scrape_target:
            token = _get_gateway_token_from_keychain()
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    r = await client.post(
                        f"{GATEWAY_BASE}/fetch",
                        json={"url": scrape_target["url"]},
                        headers={"X-Jarvis-Token": token}
                    )
                scraped = r.json().get("text_excerpt", "")
                prompt  = f"{scrape_target['prompt']}\n\n{scraped[:3000]}"
                async with httpx.AsyncClient() as client:
                    r = await client.post(
                        "http://localhost:11434/api/generate",
                        json={"model": "llama3.1:8b", "prompt": prompt, "stream": False},
                        timeout=60
                    )
                text     = r.json()["response"]
                provider = f"local/llama+scrape({scrape_target['name']})"
            except Exception as e:
                text     = f"Scrape failed: {e}"
                provider = "scrape/error"
        else:
            text     = "No scrape target found"
            provider = "scrape/miss"

    elif target in ("claude", "perplexity"):
        from brain.cloud_client import ask_cloud
        provider_name = "claude" if target == "claude" else "perplexity"
        cloud_resp = await ask_cloud(provider_name, req.intent, intent=req.intent)
        text     = cloud_resp.get("response", "No response from cloud")
        provider = f"cloud/{target}"

    else:
        text     = f"Unknown routing target: {target}"
        provider = "error"

    return {
        "response": text,
        "provider": provider,
        "routing":  routing,
        "intent":   req.intent
    }


from brain.scrape_targets import find_scrape_target

class ScrapeRequest(BaseModel):
    intent: str
    complexity: int = 3

@app.post("/v1/scrape")
async def scrape_and_summarize(req: ScrapeRequest):
    target = find_scrape_target(req.intent)
    if not target:
        return {"error": "no scrape target found", "intent": req.intent}

    token = _get_gateway_token_from_keychain()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{GATEWAY_BASE}/fetch",
                json={"url": target["url"]},
                headers={"X-Jarvis-Token": token}
            )
        scraped = r.json().get("text_excerpt", "")
    except Exception as e:
        return {"error": f"scrape failed: {e}", "intent": req.intent}

    prompt = f"{target['prompt']}\n\n{scraped[:3000]}"
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3.1:8b", "prompt": prompt, "stream": False},
            timeout=60
        )
    summary = r.json()["response"]

    return {
        "response":  summary,
        "provider":  "local/llama+scrape",
        "source":    target["url"],
        "target":    target["name"],
        "intent":    req.intent
    }



import asyncpg
from datetime import timezone
from brain.code_writer import generate_with_qwen, generate_with_claude, fix_with_qwen, _inject_header
from brain.staging import write_staged, validate_syntax, validate_lint, validate_security, format_code, promote, cleanup, is_allowed_path
from brain.git_client import get_or_create_branch, stage_and_commit, push_branch, return_to_main
from brain.rate_limiter import RateLimiter
import logging
logger = logging.getLogger("jarvis.app")

code_write_limiter = RateLimiter(max_calls=10, window_seconds=3600)


class CodeWriteRequest(BaseModel):
    intent: str
    target_file: str
    context: str = ""
    branch_hint: str = "codegen"


@app.post("/v1/code/write")
async def code_write(req: CodeWriteRequest):
    from fastapi import Request
    import httpx

    if not code_write_limiter.allow():
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit: max 10 code writes/hour. Remaining: {code_write_limiter.remaining()}"
        )

    if not is_allowed_path(req.target_file):
        raise HTTPException(
            status_code=403,
            detail=f"Target path not in allowed write paths: {req.target_file}"
        )

    escalated = False
    error = None
    commit_hash = None
    diff = None
    branch = None
    syntax_ok = False
    lint_ok = False
    security_ok = False

    try:
        gen = await generate_with_qwen(req.intent, req.context)

        if not gen["ok"]:
            from brain.cloud_client import ask_cloud
            gen = await generate_with_claude(req.intent, req.context, ask_cloud)
            escalated = True

        if not gen["ok"]:
            raise ValueError(f"Generation failed: {gen.get('error')}")

        code = gen["code"]
        filename = Path(req.target_file).expanduser().name
        staged = write_staged(filename, code)

        fmt = format_code(staged)
        if not fmt["ok"]:
            cleanup(staged)
            raise ValueError(f"Formatting failed: {fmt['error']}")

        syn = validate_syntax(staged)
        syntax_ok = syn["ok"]
        if not syn["ok"]:
            cleanup(staged)
            raise ValueError(f"Syntax error: {syn['error']}")

        lint = validate_lint(staged)
        lint_ok = lint["ok"]
        if not lint["ok"]:
            fix = await fix_with_qwen(staged.read_text(), lint["error"], req.intent)
            if not fix["ok"]:
                cleanup(staged)
                raise ValueError(f"Lint error (unfixable): {lint['error']}")
            staged.write_text(fix["code"], encoding="utf-8")
            lint2 = validate_lint(staged)
            if not lint2["ok"]:
                cleanup(staged)
                raise ValueError(f"Lint error (after self-correction): {lint2['error']}")
            lint_ok = True
            logger.info("Qwen self-correction succeeded")

        sec = validate_security(staged)
        security_ok = sec["ok"]
        if not sec["ok"]:
            cleanup(staged)
            raise ValueError(f"Security error: {sec['error']}")

        timestamp = datetime.now(timezone.utc).isoformat()
        validation_summary = f"syntax ✓ | lint ✓ | bandit ✓"
        final_code = _inject_header(staged.read_text(), req.intent, timestamp, validation_summary)
        staged.write_text(final_code, encoding="utf-8")

        branch_result = get_or_create_branch(req.branch_hint)
        if not branch_result["ok"]:
            cleanup(staged)
            raise ValueError(f"Git branch error: {branch_result['error']}")
        branch = branch_result["branch"]

        promoted = promote(staged, req.target_file)
        cleanup(staged)

        commit_result = stage_and_commit(
            str(promoted),
            f"jarvis: {req.intent[:72]}"
        )
        if not commit_result["ok"]:
            raise ValueError(f"Git commit error: {commit_result['error']}")

        commit_hash = commit_result["commit_hash"]
        diff = commit_result["diff"]

        push_branch(branch)
        return_to_main()

        try:
            conn = await asyncpg.connect(
                host="localhost", port=5432,
                user="jarvis", password="jarvisdb", database="jarvis"
            )
            await conn.execute(
                """INSERT INTO code_write_log
                   (intent, target_file, branch, commit_hash, escalated, success,
                    code_len, validation_syntax, validation_lint, validation_security)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
                req.intent, req.target_file, branch, commit_hash,
                escalated, True, len(code),
                syntax_ok, lint_ok, security_ok
            )
            await conn.close()
        except Exception as log_err:
            pass

        return {
            "ok": True,
            "commit_hash": commit_hash,
            "branch": branch,
            "escalated": escalated,
            "diff": diff,
            "lines_written": len(code.splitlines()),
            "validation": {
                "syntax": syntax_ok,
                "lint": lint_ok,
                "security": security_ok,
            }
        }

    except Exception as e:
        error = str(e)
        return_to_main()

        try:
            conn = await asyncpg.connect(
                host="localhost", port=5432,
                user="jarvis", password="jarvisdb", database="jarvis"
            )
            await conn.execute(
                """INSERT INTO code_write_log
                   (intent, target_file, branch, escalated, success, error,
                    validation_syntax, validation_lint, validation_security)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
                req.intent, req.target_file, branch,
                escalated, False, error,
                syntax_ok, lint_ok, security_ok
            )
            await conn.close()
        except Exception:
            pass

        raise HTTPException(status_code=500, detail=error)


@app.get("/v1/metrics")
async def node_metrics():
    from brain.metrics import get_metrics
    return get_metrics()

@app.get("/v1/github/prs")
async def list_prs():
    from brain.github_client import get_open_prs
    return await get_open_prs()

@app.post("/v1/github/prs/{pr_number}/merge")
async def merge_pr(pr_number: int):
    from brain.github_client import merge_pr as do_merge
    return await do_merge(pr_number)

@app.post("/v1/github/prs/{pr_number}/close")
async def close_pr(pr_number: int):
    from brain.github_client import close_pr as do_close
    return await do_close(pr_number)

@app.get("/v1/code/log")
async def code_log(limit: int = 20):
    import asyncpg, os
    conn = await asyncpg.connect("postgresql://jarvis:jarvisdb@localhost:5432/jarvis")
    rows = await conn.fetch(
        "SELECT ts::text, intent, target_file as file, branch, escalated, success, "
        "validation_lint as lint, validation_security as security "
        "FROM code_write_log ORDER BY ts DESC LIMIT $1", limit
    )
    await conn.close()
    return [dict(r) for r in rows]

@app.get("/v1/agents")
async def list_agents():
    return []

@app.post("/v1/admin/restart/{node}")
async def restart_node(node: str):
    import subprocess
    if node == "brain":
        subprocess.Popen(
            "sleep 2 && launchctl kickstart -k gui/$UID/com.jarvis.brain",
            shell=True
        )
        return {"status": "restart_scheduled", "node": node}
    return {"status": "remote_restart_not_yet_implemented", "node": node}

from brain.costs import router as costs_router
app.include_router(costs_router)
