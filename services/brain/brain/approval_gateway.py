from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import psycopg2
import psycopg2.extras
import httpx
import os
from datetime import datetime, timezone

router = APIRouter()

DSN = "postgresql://jarvis:jarvisdb@localhost:5432/jarvis"
TIER_REVIEW_DAYS = {0: None, 1: 5, 2: 30, 3: 90, 4: 365}
TIER_NAMES = {0: "Unverified", 1: "Provisional", 2: "Trusted", 3: "Established", 4: "Permanent"}

def get_secret(key):
    path = os.path.expanduser("~/jarvis/.secrets")
    with open(path) as f:
        for line in f:
            if line.startswith(f"{key}="):
                return line.strip().split("=", 1)[1]
    return None

def get_conn():
    return psycopg2.connect(DSN)

class ApprovalRequest(BaseModel):
    action_type: str
    agent_id: Optional[str] = None
    payload_summary: str
    classification: Optional[str] = "20_PROJECTS"
    notes: Optional[str] = None

class DecisionRequest(BaseModel):
    decision: str
    decided_by: str
    notes: Optional[str] = None

class TrustUpdate(BaseModel):
    action_type: str
    new_tier: int
    approved_by: str
    notes: Optional[str] = None

@router.post("/v1/approvals/request")
def create_approval_request(req: ApprovalRequest):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT current_tier, max_tier, always_approve FROM trust_registry WHERE action_type = %s", (req.action_type,))
        trust = cur.fetchone()
        if not trust:
            raise HTTPException(status_code=400, detail=f"Unknown action_type: {req.action_type}")
        cur.execute("SELECT timeout_behavior FROM approval_requests LIMIT 0")
        timeout_behavior = "cancel"
        if req.action_type in ("agent_file_write", "agent_service_restart", "agent_code_deploy"):
            timeout_behavior = "proceed"
        tier = trust["current_tier"]
        always = trust["always_approve"]
        if tier > 0 and not always:
            status = "auto"
        else:
            status = "pending"
        cur.execute("""
            INSERT INTO approval_requests
                (action_type, agent_id, payload_summary, classification, timeout_behavior, status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, status, expires_at
        """, (req.action_type, req.agent_id, req.payload_summary, req.classification, timeout_behavior, status, req.notes))
        row = cur.fetchone()
        conn.commit()
        if status == "pending":
            _send_notifications(row["id"], req.action_type, req.payload_summary, "new")
        return {"id": row["id"], "status": row["status"], "expires_at": str(row["expires_at"]), "tier": tier, "tier_name": TIER_NAMES.get(tier)}
    finally:
        conn.close()

@router.get("/v1/approvals/pending")
def list_pending():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, action_type, agent_id, payload_summary, classification,
                   timeout_behavior, status, created_at, expires_at, notes
            FROM approval_requests
            WHERE status = 'pending'
            ORDER BY created_at ASC
        """)
        rows = cur.fetchall()
        now = datetime.now(timezone.utc)
        result = []
        for r in rows:
            d = dict(r)
            d["created_at"] = str(d["created_at"])
            d["expires_at"] = str(d["expires_at"])
            expires = r["expires_at"]
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            created = r["created_at"] if r["created_at"].tzinfo else r["created_at"].replace(tzinfo=timezone.utc)
            d["hours_pending"] = round((now - created).total_seconds() / 3600, 1)
            d["hours_remaining"] = round((expires - now).total_seconds() / 3600, 1)
            result.append(d)
        return {"pending": result, "count": len(result)}
    finally:
        conn.close()

@router.get("/v1/approvals/history")
def approval_history(limit: int = 30):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, action_type, agent_id, payload_summary, status,
                   created_at, decided_at, decided_by, notes
            FROM approval_requests
            WHERE status != 'pending'
            ORDER BY created_at DESC LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["created_at"] = str(d["created_at"])
            d["decided_at"] = str(d["decided_at"]) if d["decided_at"] else None
            result.append(d)
        return {"history": result, "count": len(result)}
    finally:
        conn.close()

@router.patch("/v1/approvals/{request_id}/decide")
def decide_request(request_id: int, dec: DecisionRequest):
    if dec.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, status, action_type FROM approval_requests WHERE id = %s", (request_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")
        if row["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Request is already {row['status']}")
        cur.execute("""
            UPDATE approval_requests
            SET status = %s, decided_at = NOW(), decided_by = %s, notes = %s
            WHERE id = %s
        """, (dec.decision, dec.decided_by, dec.notes, request_id))
        if dec.decision == "approved":
            cur.execute("""
                UPDATE trust_registry
                SET escalation_count = escalation_count + 1
                WHERE action_type = %s
            """, (row["action_type"],))
        conn.commit()
        return {"id": request_id, "status": dec.decision, "decided_by": dec.decided_by}
    finally:
        conn.close()

@router.get("/v1/approvals/trust")
def list_trust_registry():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM trust_registry ORDER BY action_type")
        rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tier_name"] = TIER_NAMES.get(d["current_tier"], "Unknown")
            d["approved_at"] = str(d["approved_at"]) if d["approved_at"] else None
            d["next_review_at"] = str(d["next_review_at"]) if d["next_review_at"] else None
            result.append(d)
        return {"trust_registry": result}
    finally:
        conn.close()

@router.patch("/v1/approvals/trust/update")
def update_trust(req: TrustUpdate):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT max_tier, always_approve FROM trust_registry WHERE action_type = %s", (req.action_type,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Action type not found")
        if req.new_tier > row["max_tier"]:
            raise HTTPException(status_code=400, detail=f"Tier {req.new_tier} exceeds max_tier {row['max_tier']} for {req.action_type}")
        review_days = TIER_REVIEW_DAYS.get(req.new_tier)
        next_review = f"NOW() + INTERVAL '{review_days} days'" if review_days else "NULL"
        cur.execute(f"""
            UPDATE trust_registry
            SET current_tier = %s, approved_by = %s, approved_at = NOW(),
                next_review_at = {next_review}, notes = %s
            WHERE action_type = %s
        """, (req.new_tier, req.approved_by, req.notes, req.action_type))
        conn.commit()
        return {"action_type": req.action_type, "new_tier": req.new_tier, "tier_name": TIER_NAMES.get(req.new_tier)}
    finally:
        conn.close()

@router.post("/v1/approvals/process-expired")
def process_expired():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, action_type, timeout_behavior FROM approval_requests
            WHERE status = 'pending' AND expires_at < NOW()
        """)
        expired = cur.fetchall()
        results = []
        for r in expired:
            final_status = "approved" if r["timeout_behavior"] == "proceed" else "rejected"
            cur.execute("""
                UPDATE approval_requests
                SET status = %s, decided_at = NOW(), decided_by = 'system_timeout', notes = 'Auto-resolved after 14-day timeout'
                WHERE id = %s
            """, (final_status, r["id"]))
            results.append({"id": r["id"], "action_type": r["action_type"], "resolved_as": final_status})
        conn.commit()
        return {"processed": len(results), "results": results}
    finally:
        conn.close()

def _send_notifications(request_id: int, action_type: str, summary: str, trigger: str):
    try:
        api_key = get_secret("SENDGRID_API_KEY")
        from_email = get_secret("JARVIS_ALERT_FROM")
        to_email = get_secret("JARVIS_ALERT_TO")
        if api_key and from_email and to_email:
            subject = f"JARVIS Approval Required: {action_type}"
            body = f"""
<h2>JARVIS Approval Request</h2>
<p><b>Action:</b> {action_type}</p>
<p><b>Summary:</b> {summary}</p>
<p><b>Request ID:</b> {request_id}</p>
<p><b>Trigger:</b> {trigger}</p>
<p>Review at: <a href="http://100.87.223.31:4000">JARVIS Dashboard → Approvals</a></p>
<p>This request will auto-resolve in 14 days.</p>
"""
            import urllib.request, json as _json
            payload = _json.dumps({
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": from_email, "name": "JARVIS"},
                "subject": subject,
                "content": [{"type": "text/html", "value": body}]
            }).encode()
            req = urllib.request.Request(
                "https://api.sendgrid.com/v3/mail/send",
                data=payload,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Notification error: {e}")
