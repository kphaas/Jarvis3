#!/usr/bin/env python3
"""
jarvis_cleanup.py — operational hygiene for JARVIS Brain
Runs nightly at 2am via LaunchAgent.
Deletes old rows per retention policy, runs VACUUM, and logs results.

Security:  No user input — fully internal scheduled script.
Resilience: Each table cleanup is independent — one failure does not
            stop the others.
"""

import psycopg2
import os
import logging
from datetime import datetime

logging.basicConfig(
    filename=os.path.expanduser("~/jarvis/logs/cleanup.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("jarvis_cleanup")


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


RETENTION = [
    ("routing_decisions",   "created_at", 30),
    ("agent_steps",         "created_at", 14),
    ("agents",              "created_at", 60),
    ("cloud_costs",         "ts",         90),
    ("quality_ratings",     "created_at", 90),
    ("circuit_breaker_log", "created_at", 30),
    ("code_write_log",      "ts",         60),
    ("child_query_log",     "created_at", 14),
]

VACUUM_TABLES = [r[0] for r in RETENTION]


def cleanup():
    log.info("=== JARVIS cleanup started ===")
    try:
        conn = get_conn()
        conn.autocommit = True
        cur = conn.cursor()

        for table, col, days in RETENTION:
            try:
                cur.execute(
                    f"DELETE FROM {table} WHERE {col} < NOW() - INTERVAL %s",
                    (f"{days} days",)
                )
                log.info(f"{table}: deleted {cur.rowcount} rows older than {days} days")
            except Exception as e:
                log.error(f"{table}: cleanup failed — {e}")

        for table in VACUUM_TABLES:
            try:
                cur.execute(f"VACUUM ANALYZE {table}")
                log.info(f"{table}: VACUUM ANALYZE complete")
            except Exception as e:
                log.error(f"{table}: VACUUM failed — {e}")

        cur.close()
        conn.close()
        log.info("=== JARVIS cleanup complete ===")

    except Exception as e:
        log.error(f"Cleanup aborted — DB connection failed: {e}")


if __name__ == "__main__":
    cleanup()
