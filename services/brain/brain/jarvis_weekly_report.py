#!/usr/bin/env python3
"""
jarvis_weekly_report.py — Phase 5b
Sends a weekly Monday 7am HTML email to Ken with:
  - Flagged queries from Ryleigh and Sloane
  - Routing stats for the week
  - Provider health snapshot
  - Circuit breaker events

Security:  SendGrid API key read from .secrets only, never hardcoded.
           No query content logged to disk, only emailed to Ken.
Resilience: If SendGrid fails, logs error and exits cleanly.
            Report generates even if some DB queries fail.
"""

import os
import json
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime

logging.basicConfig(
    filename=os.path.expanduser("~/jarvis/logs/weekly_report.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("jarvis_report")


def get_secret(key):
    secrets_path = os.path.expanduser("~/jarvis/.secrets")
    try:
        with open(secrets_path) as f:
            for line in f:
                if line.startswith(key + "="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return ""


def get_conn():
    return psycopg2.connect(
        host="localhost", port=5432,
        dbname="jarvis", user="jarvis",
        password=get_secret("POSTGRES_PASSWORD"),
        connect_timeout=5
    )


def get_flagged_queries():
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT user_name, query, flag_reason, flag_triggers,
                   provider_used, was_blocked, created_at
            FROM child_query_log
            WHERE created_at > NOW() - INTERVAL '7 days'
            ORDER BY user_name, created_at DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        log.error(f"get_flagged_queries failed: {e}")
        return []


def get_routing_summary():
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT provider_chosen, COUNT(*) as total,
                   ROUND(AVG(latency_ms)) as avg_ms
            FROM routing_decisions
            WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY provider_chosen ORDER BY total DESC
        """)
        by_provider = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT
                SUM(CASE WHEN provider_chosen IN
                    ('endpoint_llama','qwen','scrape') THEN 1 ELSE 0 END) as local,
                SUM(CASE WHEN provider_chosen NOT IN
                    ('endpoint_llama','qwen','scrape') THEN 1 ELSE 0 END) as cloud,
                COUNT(*) as total
            FROM routing_decisions
            WHERE created_at > NOW() - INTERVAL '7 days'
        """)
        totals = dict(cur.fetchone())

        cur.execute("""
            SELECT provider, event, failure_count, triggered_by, created_at
            FROM circuit_breaker_log
            WHERE created_at > NOW() - INTERVAL '7 days'
            ORDER BY created_at DESC
        """)
        circuit_events = [dict(r) for r in cur.fetchall()]

        cur.close()
        conn.close()
        return {"by_provider": by_provider, "totals": totals, "circuit_events": circuit_events}
    except Exception as e:
        log.error(f"get_routing_summary failed: {e}")
        return {}


def build_html(flagged, routing, report_date):
    if flagged:
        ryleigh_rows = [r for r in flagged if r["user_name"].lower() == "ryleigh"]
        sloane_rows  = [r for r in flagged if r["user_name"].lower() == "sloane"]

        def make_table(rows, name):
            if not rows:
                return f"<p style='color:#666'>No flagged queries for {name} this week.</p>"
            html = """<table width='100%' cellpadding='8'
                style='border-collapse:collapse;font-size:13px'>
                <tr style='background:#1a1a2e;color:white'>
                <th align='left'>Time</th><th align='left'>Query</th>
                <th align='left'>Flag Reason</th><th align='left'>Blocked?</th></tr>"""
            for i, r in enumerate(rows):
                bg      = "#f8f8f8" if i % 2 == 0 else "white"
                blocked = "Yes" if r["was_blocked"] else "Logged"
                ts      = r["created_at"].strftime("%a %b %d %I:%M%p") if hasattr(r["created_at"], "strftime") else str(r["created_at"])
                q       = str(r["query"])[:120].replace("<","&lt;").replace(">","&gt;")
                html   += f"<tr style='background:{bg}'><td style='color:#666;white-space:nowrap'>{ts}</td><td><strong>{q}</strong></td><td style='color:#c0392b'>{r['flag_reason']}</td><td>{blocked}</td></tr>"
            return html + "</table>"

        flags_html = f"""
        <h2 style='color:#c0392b'>Flagged Queries This Week</h2>
        <h3>Ryleigh ({len(ryleigh_rows)} flags)</h3>{make_table(ryleigh_rows, 'Ryleigh')}
        <h3>Sloane ({len(sloane_rows)} flags)</h3>{make_table(sloane_rows, 'Sloane')}"""
    else:
        flags_html = "<h2 style='color:#27ae60'>No Flagged Queries This Week</h2><p style='color:#666'>Ryleigh and Sloane had no flagged or blocked queries this week.</p>"

    totals    = routing.get("totals", {})
    total     = totals.get("total", 0) or 0
    local     = totals.get("local", 0) or 0
    cloud     = totals.get("cloud", 0) or 0
    local_pct = round((local / total * 100) if total > 0 else 0)

    provider_rows = ""
    for p in routing.get("by_provider", []):
        provider_rows += f"<tr><td>{p['provider_chosen']}</td><td>{p['total']}</td><td>{p['avg_ms']}ms</td></tr>"

    circuit_html = ""
    for e in routing.get("circuit_events", []):
        ts = e["created_at"].strftime("%a %b %d %I:%M%p") if hasattr(e["created_at"], "strftime") else str(e["created_at"])
        circuit_html += f"<li>{ts} — <strong>{e['provider']}</strong> {e['event']} (failures: {e['failure_count']})</li>"
    circuit_section = f"<ul>{circuit_html}</ul>" if circuit_html else "<p style='color:#666'>No circuit breaker events this week.</p>"

    return f"""<!DOCTYPE html><html><body style='font-family:Arial,sans-serif;max-width:800px;margin:0 auto;padding:20px;background:#f5f5f5'>
    <div style='background:#1a1a2e;color:white;padding:20px;border-radius:8px 8px 0 0'>
        <h1 style='margin:0'>JARVIS Weekly Report</h1>
        <p style='margin:5px 0 0;color:#aaa'>{report_date}</p>
    </div>
    <div style='background:white;padding:20px;border-radius:0 0 8px 8px;box-shadow:0 2px 4px rgba(0,0,0,0.1)'>
        {flags_html}
        <hr style='border:1px solid #eee;margin:20px 0'>
        <h2 style='color:#2c3e50'>Routing Summary (Last 7 Days)</h2>
        <p>Total: <strong>{total}</strong> &nbsp;|&nbsp; Local: <strong>{local} ({local_pct}%)</strong> &nbsp;|&nbsp; Cloud: <strong>{cloud}</strong></p>
        <table width='50%' cellpadding='8' style='border-collapse:collapse;font-size:13px'>
            <tr style='background:#1a1a2e;color:white'><th align='left'>Provider</th><th align='left'>Requests</th><th align='left'>Avg Latency</th></tr>
            {provider_rows}
        </table>
        <hr style='border:1px solid #eee;margin:20px 0'>
        <h2 style='color:#2c3e50'>Circuit Breaker Events</h2>
        {circuit_section}
        <hr style='border:1px solid #eee;margin:20px 0'>
        <p style='color:#999;font-size:11px'>Sent by JARVIS Brain · {report_date}</p>
    </div></body></html>"""


def send_email(subject, html_body):
    import urllib.request
    api_key    = get_secret("SENDGRID_API_KEY")
    from_email = get_secret("JARVIS_ALERT_FROM")
    to_email   = get_secret("JARVIS_ALERT_TO")

    if not all([api_key, from_email, to_email]):
        log.error("Missing SendGrid secrets")
        return False

    payload = json.dumps({
        "personalizations": [{"to": [{"email": to_email}]}],
        "from":    {"email": from_email, "name": "JARVIS"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_body}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 202:
                log.info(f"Email sent to {to_email}")
                return True
            log.error(f"SendGrid status {resp.status}")
            return False
    except Exception as e:
        log.error(f"SendGrid failed: {e}")
        return False


def mark_reviewed():
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE child_query_log SET reviewed = TRUE
            WHERE created_at > NOW() - INTERVAL '7 days' AND reviewed = FALSE
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        log.error(f"mark_reviewed failed: {e}")


def run():
    report_date = datetime.now().strftime("%A, %B %d %Y at %I:%M %p")
    log.info(f"Generating weekly report — {report_date}")
    flagged = get_flagged_queries()
    routing = get_routing_summary()
    html    = build_html(flagged, routing, report_date)
    subject = f"JARVIS Weekly Report — {len(flagged)} flagged queries" if flagged else "JARVIS Weekly Report — all clear"
    ok = send_email(subject, html)
    if ok:
        mark_reviewed()
        log.info("Weekly report complete")
    else:
        log.error("Weekly report failed — email not sent")


if __name__ == "__main__":
    run()
