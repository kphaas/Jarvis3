"""
adaptive_router.py — Phase 5b
Weight engine, circuit breaker, fallback chains, and decision logging.
All routing decisions flow through this module.

Security:  All DB writes use parameterized queries — no string interpolation.
Resilience: Every DB call is wrapped in try/except — this module never crashes Brain.
"""

import json
import os
import psycopg2
import psycopg2.extras
import psycopg2.pool
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Helpers — secret loading and DB connection
# Reuses Brain's existing .secrets pattern, no new dependencies
# ---------------------------------------------------------------------------

def _get_secret(key: str) -> str:
    """Read a secret from ~/jarvis/.secrets file."""
    secrets_path = os.path.expanduser("~/jarvis/.secrets")
    try:
        with open(secrets_path) as f:
            for line in f:
                if line.startswith(f"{key}="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return ""


# Module-level connection pool — created once on first use, reused forever.
# minconn=2 keeps 2 warm connections ready at all times.
# maxconn=10 hard-caps Brain's Postgres usage regardless of load.
_pool = None


def _get_pool():
    """Return the module-level pool, creating it if needed."""
    global _pool
    if _pool is None or _pool.closed:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            host="localhost",
            port=5432,
            dbname="jarvis",
            user="jarvis",
            password=_get_secret("POSTGRES_PASSWORD"),
            connect_timeout=3
        )
    return _pool


def _get_conn():
    """Borrow a connection from the pool."""
    return _get_pool().getconn()


def _put_conn(conn) -> None:
    """Return a connection to the pool after use. Always call this after _get_conn()."""
    try:
        _get_pool().putconn(conn)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Keyword sets — mirrored from router.py so simulate_route stays in sync
# ---------------------------------------------------------------------------

CODE_KEYWORDS = {
    "code", "write", "fix", "debug", "function", "script",
    "refactor", "implement", "class", "def", "import",
    "python", "javascript", "bash", "sql", "dockerfile", "regex"
}

SCRAPE_KEYWORDS = {
    "weather", "forecast", "temperature", "rain", "sunny",
    "uga", "dawgs", "bulldogs", "soccer", "fifa",
    "atlanta", "alpharetta", "johns creek", "roswell",
    "college football", "cfb", "olympics", "unraid",
    "events", "things to do", "weekend"
}

SEARCH_KEYWORDS = {
    "who is", "what is", "search", "find", "lookup",
    "tell me about", "research",
    "news", "headlines", "latest news", "today",
    "score", "scores", "standings",
    "stocks", "market", "nasdaq", "dow", "s&p",
    "price of", "how much is", "current price",
    "spacex", "tesla", "apple", "google", "microsoft"
}


# ---------------------------------------------------------------------------
# Fallback chains — ordered list of providers to try per tool on failure
# Primary is index 0. If it fails, index 1 is tried, then index 2.
# ---------------------------------------------------------------------------

FALLBACK_CHAINS = {
    "news":       ["newsapi", "perplexity", "claude"],
    "sports":     ["espn", "thesportsdb", "perplexity"],
    "ask":        ["perplexity", "claude", "endpoint_llama"],
    "web_search": ["wikipedia", "duckduckgo", "perplexity"],
}

# Cost factors used in weight recalculation.
# Local providers cost nothing so they get no penalty.
# Cloud providers get a small cost penalty to prefer local when equal quality.
COST_FACTORS = {
    "endpoint_llama": 1.0,
    "qwen":           1.0,
    "scrape":         1.0,
    "perplexity":     0.85,
    "claude":         0.90,
}

# Safe defaults used when DB is unreachable
DEFAULT_WEIGHTS = {
    "endpoint_llama": 1.0,
    "perplexity":     1.0,
    "claude":         1.0,
    "qwen":           1.0,
    "scrape":         1.0,
}


# ---------------------------------------------------------------------------
# Weight loading
# ---------------------------------------------------------------------------

def load_weights() -> dict:
    """
    Load current provider weights from DB.
    Returns default equal weights on any DB failure so routing continues.
    """
    try:
        conn = _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT provider, weight, locked, circuit_open
            FROM provider_weights
        """)
        rows = cur.fetchall()
        cur.close()
        _put_conn(conn)
        if not rows:
            return {k: {"weight": v, "locked": False, "circuit_open": False}
                    for k, v in DEFAULT_WEIGHTS.items()}
        return {
            r["provider"]: {
                "weight": float(r["weight"]),
                "locked": r["locked"],
                "circuit_open": r["circuit_open"]
            }
            for r in rows
        }
    except Exception:
        return {k: {"weight": v, "locked": False, "circuit_open": False}
                for k, v in DEFAULT_WEIGHTS.items()}


# ---------------------------------------------------------------------------
# Circuit breaker — check, trip, and reset per provider
# ---------------------------------------------------------------------------

def is_circuit_open(provider: str) -> bool:
    """Returns True if this provider is tripped and must not be used."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT circuit_open FROM provider_weights WHERE provider = %s",
            (provider,)
        )
        row = cur.fetchone()
        cur.close()
        _put_conn(conn)
        return bool(row and row[0])
    except Exception:
        return False


def record_failure(provider: str, task_id: Optional[str] = None) -> bool:
    """
    Records a provider failure and checks if the circuit breaker should trip.
    Returns True if the circuit was just tripped — caller should surface alert.
    Window resets automatically when the configured window_minutes has elapsed.
    """
    try:
        conn = _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT circuit_failure_count, circuit_window_start,
                   circuit_threshold, circuit_window_minutes, circuit_open
            FROM provider_weights
            WHERE provider = %s
        """, (provider,))
        row = cur.fetchone()
        if not row:
            cur.close()
            _put_conn(conn)
            return False

        now = datetime.now(timezone.utc)
        window_start = row["circuit_window_start"]
        if window_start.tzinfo is None:
            window_start = window_start.replace(tzinfo=timezone.utc)

        elapsed_minutes = (now - window_start).total_seconds() / 60

        if elapsed_minutes > row["circuit_window_minutes"]:
            # Window expired — reset counter, start new window, log failure
            cur.execute("""
                UPDATE provider_weights
                SET circuit_failure_count = 1,
                    circuit_window_start  = NOW(),
                    failure_count         = failure_count + 1,
                    last_updated          = NOW()
                WHERE provider = %s
            """, (provider,))
            conn.commit()
            cur.close()
            _put_conn(conn)
            return False

        new_count = row["circuit_failure_count"] + 1
        tripped = new_count >= row["circuit_threshold"] and not row["circuit_open"]

        if tripped:
            # Trip the breaker and write to circuit log
            cur.execute("""
                UPDATE provider_weights
                SET circuit_failure_count = %s,
                    circuit_open          = TRUE,
                    failure_count         = failure_count + 1,
                    last_updated          = NOW()
                WHERE provider = %s
            """, (new_count, provider))
            cur.execute("""
                INSERT INTO circuit_breaker_log
                    (provider, event, failure_count, triggered_by)
                VALUES (%s, 'tripped', %s, 'system')
            """, (provider, new_count))
        else:
            cur.execute("""
                UPDATE provider_weights
                SET circuit_failure_count = %s,
                    failure_count         = failure_count + 1,
                    last_updated          = NOW()
                WHERE provider = %s
            """, (new_count, provider))

        conn.commit()
        cur.close()
        _put_conn(conn)
        return tripped
    except Exception:
        return False


def record_success(provider: str) -> None:
    """Records a successful provider call — feeds weight recalculation."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE provider_weights
            SET success_count = success_count + 1,
                last_updated  = NOW()
            WHERE provider = %s
        """, (provider,))
        conn.commit()
        cur.close()
        _put_conn(conn)
    except Exception:
        pass


def reset_circuit(provider: str, triggered_by: str = "manual") -> bool:
    """
    Manually reset a tripped circuit breaker.
    Called from the dashboard reset button or the API endpoint.
    """
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE provider_weights
            SET circuit_open          = FALSE,
                circuit_failure_count = 0,
                circuit_window_start  = NOW(),
                last_updated          = NOW()
            WHERE provider = %s
        """, (provider,))
        cur.execute("""
            INSERT INTO circuit_breaker_log
                (provider, event, failure_count, triggered_by)
            VALUES (%s, 'reset', 0, %s)
        """, (provider, triggered_by))
        conn.commit()
        cur.close()
        _put_conn(conn)
        return True
    except Exception:
        return False


def update_circuit_thresholds(
    provider: str,
    threshold: int,
    window_minutes: int
) -> bool:
    """Update circuit breaker thresholds for a provider from the dashboard."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE provider_weights
            SET circuit_threshold      = %s,
                circuit_window_minutes = %s,
                last_updated           = NOW()
            WHERE provider = %s
        """, (threshold, window_minutes, provider))
        conn.commit()
        cur.close()
        _put_conn(conn)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Decision logging — every routing decision written to DB with full reasoning
# ---------------------------------------------------------------------------

def log_decision(
    intent: str,
    complexity: int,
    provider: str,
    reason: str,
    task_id: Optional[str],
    latency_ms: Optional[int],
    success: Optional[bool],
    weights_snapshot: Optional[dict]
) -> Optional[int]:
    """
    Writes a routing decision to routing_decisions table.
    Returns the new row ID so callers can link quality ratings later.
    Returns None on any failure — never raises.
    """
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO routing_decisions
                (task_id, intent, complexity, provider_chosen, reason,
                 weights_snapshot, latency_ms, success)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            task_id,
            intent[:500],
            complexity,
            provider,
            reason[:500],
            json.dumps(weights_snapshot) if weights_snapshot else None,
            latency_ms,
            success
        ))
        row_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        _put_conn(conn)
        return row_id
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Quality ratings — thumbs up / thumbs down from dashboard
# ---------------------------------------------------------------------------

def record_rating(
    task_id: str,
    rating: int,
    provider: str,
    decision_id: Optional[int] = None
) -> bool:
    """
    Record a quality rating for a completed routing decision.
    rating: 1 = thumbs up, -1 = thumbs down.

    Thumbs down immediately nudges weight down (floor 0.1, proportional penalty).
    Thumbs up immediately nudges weight up (ceiling 2.0, small bonus).
    Locked providers are never penalized.
    Full recalculation still happens on the 24hr schedule.
    """
    try:
        conn = _get_conn()
        cur = conn.cursor()

        # Store the rating record
        cur.execute("""
            INSERT INTO quality_ratings
                (task_id, routing_decision_id, provider, rating)
            VALUES (%s, %s, %s, %s)
        """, (task_id, decision_id, provider, rating))

        # Update running quality totals on the provider
        cur.execute("""
            UPDATE provider_weights
            SET quality_sum   = quality_sum + %s,
                quality_count = quality_count + 1,
                last_updated  = NOW()
            WHERE provider = %s
        """, (rating, provider))

        # Apply immediate weight nudge
        if rating == -1:
            cur.execute("""
                UPDATE provider_weights
                SET weight       = GREATEST(0.1, weight - 0.05),
                    last_updated = NOW()
                WHERE provider = %s AND locked = FALSE
            """, (provider,))
        elif rating == 1:
            cur.execute("""
                UPDATE provider_weights
                SET weight       = LEAST(2.0, weight + 0.02),
                    last_updated = NOW()
                WHERE provider = %s AND locked = FALSE
            """, (provider,))

        conn.commit()
        cur.close()
        _put_conn(conn)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Weight recalculation — 24hr schedule or manual trigger
# ---------------------------------------------------------------------------

def recalculate_weights() -> dict:
    """
    Recomputes weights for all unlocked providers from stored history.
    Formula: success_rate * quality_factor * cost_factor
    Locked providers are skipped and noted in the returned summary.
    Weight floor = 0.1, ceiling = 2.0.
    """
    try:
        conn = _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT provider, success_count, failure_count,
                   quality_sum, quality_count, locked
            FROM provider_weights
        """)
        rows = cur.fetchall()
        summary = {}

        for r in rows:
            if r["locked"]:
                summary[r["provider"]] = {"status": "skipped — weight is locked"}
                continue

            total = (r["success_count"] or 0) + (r["failure_count"] or 0)
            # Default to 0.8 when no history exists yet
            success_rate = r["success_count"] / total if total > 0 else 0.8

            quality_count = r["quality_count"] or 0
            quality_sum   = r["quality_sum"] or 0
            if quality_count > 0:
                # Ratings are -1/+1 — normalize to 0.5–1.5 multiplier range
                avg_quality    = quality_sum / quality_count
                quality_factor = 1.0 + (avg_quality * 0.25)
                quality_factor = max(0.5, min(1.5, quality_factor))
            else:
                quality_factor = 1.0

            cost_factor = COST_FACTORS.get(r["provider"], 1.0)
            new_weight  = round(success_rate * quality_factor * cost_factor, 4)
            new_weight  = max(0.1, min(2.0, new_weight))

            upd = conn.cursor()
            upd.execute("""
                UPDATE provider_weights
                SET weight = %s, last_updated = NOW()
                WHERE provider = %s
            """, (new_weight, r["provider"]))
            upd.close()

            summary[r["provider"]] = {
                "new_weight":    new_weight,
                "success_rate":  round(success_rate, 3),
                "quality_factor": round(quality_factor, 3),
                "cost_factor":   cost_factor,
            }

        conn.commit()
        cur.close()
        _put_conn(conn)
        return summary
    except Exception as e:
        return {"error": str(e)}


def set_weight(provider: str, weight: float, locked: bool) -> bool:
    """Manually override a provider weight and lock state from the dashboard."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE provider_weights
            SET weight       = %s,
                locked       = %s,
                last_updated = NOW()
            WHERE provider = %s
        """, (max(0.1, min(2.0, weight)), locked, provider))
        conn.commit()
        cur.close()
        _put_conn(conn)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Simulate / dry-run — full routing decision without any execution
# ---------------------------------------------------------------------------

def simulate_route(intent: str, complexity: int) -> dict:
    """
    Returns exactly what the router WOULD choose without executing anything.
    Includes step-by-step reasoning and current weight snapshot.
    Used by POST /v1/router/simulate for dry-run testing.
    """
    weights = load_weights()
    weights_summary = {
        k: v["weight"] if isinstance(v, dict) else v
        for k, v in weights.items()
    }

    lower   = intent.lower()
    tokens  = set(lower.split())
    reasoning = []
    target  = None

    # Step 1 — keyword and complexity matching (mirrors router.py logic)
    if tokens & CODE_KEYWORDS or any(k in lower for k in CODE_KEYWORDS):
        target = "qwen"
        reasoning.append("step 1: code keyword matched → qwen (free, local)")
    elif complexity <= 2:
        target = "endpoint_llama"
        reasoning.append(f"step 1: complexity {complexity} ≤ 2 → endpoint_llama (free, local)")
    elif any(k in lower for k in SCRAPE_KEYWORDS):
        target = "scrape"
        reasoning.append("step 1: scrape keyword matched → scrape (free)")
    elif any(k in lower for k in SEARCH_KEYWORDS):
        target = "perplexity"
        reasoning.append("step 1: search keyword matched → perplexity")
    elif complexity >= 4:
        target = "claude"
        reasoning.append(f"step 1: complexity {complexity} ≥ 4 → claude")
    else:
        target = "perplexity"
        reasoning.append(f"step 1: complexity {complexity} = 3, no keyword → perplexity (default)")

    # Step 2 — circuit breaker check on chosen target
    provider_data = weights.get(target, {})
    circuit_open  = provider_data.get("circuit_open", False) if isinstance(provider_data, dict) else False

    if circuit_open:
        reasoning.append(f"step 2: ⚠️  {target} circuit breaker is OPEN — selecting fallback")
        available = [
            p for p, v in weights.items()
            if isinstance(v, dict) and not v.get("circuit_open") and p != target
        ]
        if available:
            target = available[0]
            reasoning.append(f"step 2: fallback selected → {target}")
        else:
            reasoning.append("step 2: ⚠️  ALL providers circuit open — using original target anyway")
    else:
        w = weights_summary.get(target, 1.0)
        reasoning.append(f"step 2: circuit closed ✓  weight={w} → confirmed {target}")

    return {
        "would_choose":              target,
        "reasoning":                 reasoning,
        "weights_at_decision_time":  weights_summary,
        "complexity":                complexity,
        "intent_preview":            intent[:200],
        "dry_run":                   True
    }


# ---------------------------------------------------------------------------
# Replay — re-runs routing logic against a past stored decision
# ---------------------------------------------------------------------------

def replay_decision(decision_id: int) -> dict:
    """
    Fetches a past routing decision by ID and re-simulates it with
    today's weights. Returns both the original decision and the new result
    so you can see if the router would choose differently now.
    """
    try:
        conn = _get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, task_id, intent, complexity, provider_chosen,
                   reason, weights_snapshot, latency_ms, success, created_at
            FROM routing_decisions
            WHERE id = %s
        """, (decision_id,))
        row = cur.fetchone()
        cur.close()
        _put_conn(conn)

        if not row:
            return {"error": f"decision_id {decision_id} not found"}

        original            = dict(row)
        original["created_at"] = original["created_at"].isoformat()

        current_sim = simulate_route(
            intent     = row["intent"],
            complexity = row["complexity"] or 3
        )

        return {
            "original_decision":              original,
            "replayed_with_current_weights":  current_sim,
            "decision_changed":               original["provider_chosen"] != current_sim["would_choose"]
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Recent decisions — paginated feed for the dashboard live request panel
# ---------------------------------------------------------------------------

def get_recent_decisions(limit: int = 15, offset: int = 0) -> list:
    """
    Returns recent routing decisions for the dashboard live feed.
    Default page size 15 with offset-based pagination for scroll-back.
    Joins quality_ratings so the feed shows thumbs up/down inline.
    """
    try:
        conn = _get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
                rd.id,
                rd.task_id,
                rd.intent,
                rd.complexity,
                rd.provider_chosen,
                rd.reason,
                rd.latency_ms,
                rd.success,
                rd.created_at,
                qr.rating
            FROM routing_decisions rd
            LEFT JOIN quality_ratings qr ON qr.task_id = rd.task_id
            ORDER BY rd.created_at DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        rows = cur.fetchall()
        cur.close()
        _put_conn(conn)
        result = []
        for r in rows:
            d = dict(r)
            d["created_at"] = d["created_at"].isoformat()
            result.append(d)
        return result
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Stats summary — full analytics payload for the dashboard routing tab
# ---------------------------------------------------------------------------

def get_routing_stats(hours: int = 24) -> dict:
    """
    Returns a complete analytics payload for the dashboard routing tab.
    Includes: per-provider stats, complexity breakdown, local vs cloud split,
    provider health cards, and the last 20 circuit breaker events.
    """
    try:
        conn = _get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Per-provider totals, success rate, and latency stats
        cur.execute("""
            SELECT
                provider_chosen,
                COUNT(*)                                           AS total,
                SUM(CASE WHEN success THEN 1 ELSE 0 END)          AS successes,
                ROUND(AVG(latency_ms))                            AS avg_latency_ms,
                MIN(latency_ms)                                   AS min_latency_ms,
                MAX(latency_ms)                                   AS max_latency_ms
            FROM routing_decisions
            WHERE created_at > NOW() - (%s || ' hours')::INTERVAL
            GROUP BY provider_chosen
            ORDER BY total DESC
        """, (str(hours),))
        by_provider = [dict(r) for r in cur.fetchall()]

        # Average latency broken down by complexity band
        cur.execute("""
            SELECT
                complexity,
                ROUND(AVG(latency_ms)) AS avg_latency_ms,
                COUNT(*)               AS total
            FROM routing_decisions
            WHERE created_at > NOW() - (%s || ' hours')::INTERVAL
              AND complexity IS NOT NULL
            GROUP BY complexity
            ORDER BY complexity
        """, (str(hours),))
        by_complexity = [dict(r) for r in cur.fetchall()]

        # Local vs cloud split
        cur.execute("""
            SELECT
                CASE WHEN provider_chosen IN ('endpoint_llama', 'qwen', 'scrape')
                     THEN 'local' ELSE 'cloud' END AS tier,
                COUNT(*) AS total
            FROM routing_decisions
            WHERE created_at > NOW() - (%s || ' hours')::INTERVAL
            GROUP BY tier
        """, (str(hours),))
        local_vs_cloud = [dict(r) for r in cur.fetchall()]

        # Full provider health — weights, circuit state, thresholds
        cur.execute("""
            SELECT
                provider,
                weight,
                locked,
                circuit_open,
                success_count,
                failure_count,
                circuit_threshold,
                circuit_window_minutes,
                circuit_failure_count,
                last_updated
            FROM provider_weights
            ORDER BY provider
        """)
        provider_health = []
        for r in cur.fetchall():
            d = dict(r)
            d["last_updated"] = d["last_updated"].isoformat()
            provider_health.append(d)

        # Last 20 circuit breaker events for the event log
        cur.execute("""
            SELECT provider, event, failure_count, triggered_by, created_at
            FROM circuit_breaker_log
            ORDER BY created_at DESC
            LIMIT 20
        """)
        circuit_log = []
        for r in cur.fetchall():
            d = dict(r)
            d["created_at"] = d["created_at"].isoformat()
            circuit_log.append(d)

        cur.close()
        _put_conn(conn)

        return {
            "by_provider":    by_provider,
            "by_complexity":  by_complexity,
            "local_vs_cloud": local_vs_cloud,
            "provider_health": provider_health,
            "circuit_log":    circuit_log,
            "window_hours":   hours
        }
    except Exception as e:
        return {"error": str(e)}
