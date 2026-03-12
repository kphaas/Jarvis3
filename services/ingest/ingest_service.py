import os
import logging
import threading
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from feed_fetcher import fetch_feed
from summarizer import summarize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.expanduser("~/jarvis/logs/ingest.log")),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("ingest_service")

app = FastAPI()

DB_DSN = os.environ.get("JARVIS_DB_DSN", "host=localhost port=5432 dbname=jarvis user=jarvisbrain")

ingest_state = {"running": False, "last_run": None, "last_result": None}


def get_db():
    return psycopg2.connect(DB_DSN, cursor_factory=psycopg2.extras.RealDictCursor)


def run_ingest_job():
    ingest_state["running"] = True
    items_fetched = 0
    items_summarized = 0
    errors = 0
    run_start = datetime.now(timezone.utc)
    log.info("Ingest job started")

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, url, name FROM feed_sources WHERE active = true")
                sources = [dict(r) for r in cur.fetchall()]

            for source in sources:
                entries = fetch_feed(source["id"], source["url"])
                for entry in entries:
                    if not entry.get("url") or not entry.get("raw_content"):
                        continue
                    if len(entry["raw_content"].strip()) < 50:
                        continue
                    try:
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO raw_ingest_items (source_id, title, url, raw_content, published_at)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (url) DO NOTHING
                                RETURNING id
                            """, (entry["source_id"], entry["title"], entry["url"],
                                  entry["raw_content"], entry["published_at"]))
                            row = cur.fetchone()
                            conn.commit()
                            if not row:
                                continue
                            item_id = row["id"]
                            items_fetched += 1
                    except Exception as e:
                        log.error(f"DB insert failed: {e}")
                        errors += 1
                        continue

                    result = summarize(entry["raw_content"])
                    if result:
                        try:
                            with conn.cursor() as cur:
                                cur.execute("""
                                    INSERT INTO processed_summaries (item_id, summary, tags)
                                    VALUES (%s, %s, %s)
                                    ON CONFLICT DO NOTHING
                                """, (item_id, result["summary"], psycopg2.extras.Json(result["tags"])))
                                conn.commit()
                                items_summarized += 1
                        except Exception as e:
                            log.error(f"Summary insert failed: {e}")
                            errors += 1

                with conn.cursor() as cur:
                    cur.execute("UPDATE feed_sources SET last_fetched = now() WHERE id = %s", (source["id"],))
                    conn.commit()

            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ingest_run_logs (started_at, completed_at, items_fetched, items_summarized, errors)
                    VALUES (%s, now(), %s, %s, %s)
                """, (run_start, items_fetched, items_summarized, errors))
                conn.commit()

    except Exception as e:
        log.error(f"Ingest job failed: {e}")
        errors += 1
    finally:
        result = {"items_fetched": items_fetched, "items_summarized": items_summarized, "errors": errors}
        ingest_state["running"] = False
        ingest_state["last_run"] = datetime.now(timezone.utc).isoformat()
        ingest_state["last_result"] = result
        log.info(f"Ingest complete: fetched={items_fetched} summarized={items_summarized} errors={errors}")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "ingest",
        "ingest_running": ingest_state["running"],
        "last_run": ingest_state["last_run"],
        "last_result": ingest_state["last_result"],
        "ts": datetime.now(timezone.utc).isoformat()
    }


@app.get("/v1/ingest/status")
async def ingest_status():
    return ingest_state


@app.post("/v1/ingest/run")
async def run_ingest():
    if ingest_state["running"]:
        raise HTTPException(status_code=409, detail="Ingest already running")
    thread = threading.Thread(target=run_ingest_job, daemon=True)
    thread.start()
    return {"status": "started", "message": "Ingest running in background"}


@app.get("/v1/ingest/sources")
async def get_sources():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, url, name, category, active, last_fetched FROM feed_sources ORDER BY category, name")
            return {"sources": [dict(r) for r in cur.fetchall()]}


@app.post("/v1/ingest/sources")
async def add_source(body: dict):
    url = body.get("url", "").strip()
    name = body.get("name", "").strip()
    category = body.get("category", "general").strip()
    if not url or not name:
        raise HTTPException(status_code=400, detail="url and name required")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feed_sources (url, name, category) VALUES (%s, %s, %s) ON CONFLICT (url) DO NOTHING RETURNING id",
                (url, name, category)
            )
            conn.commit()
    return {"status": "ok"}


@app.get("/v1/ingest/latest")
async def get_latest():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ps.id, ri.title, ri.url, ri.published_at,
                       ps.summary, ps.tags, ps.processed_at, fs.category, fs.name as source_name
                FROM processed_summaries ps
                JOIN raw_ingest_items ri ON ri.id = ps.item_id
                JOIN feed_sources fs ON fs.id = ri.source_id
                ORDER BY ps.processed_at DESC LIMIT 20
            """)
            return {"summaries": [dict(r) for r in cur.fetchall()]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ingest_service:app", host="0.0.0.0", port=8185, reload=False)
