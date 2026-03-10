import psycopg2
from datetime import datetime, timedelta

def _get_pg_password():
    import os
    secrets_path = os.path.expanduser("~/jarvis/.secrets")
    try:
        with open(secrets_path) as f:
            for line in f:
                if line.startswith("POSTGRES_PASSWORD="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return ""

def get_db_connection():
    import os
    pw = _get_pg_password()
    dsn = f"host=localhost port=5432 dbname=jarvis user=jarvisbrain password={pw}" if pw else "host=localhost port=5432 dbname=jarvis user=jarvisbrain"
    return psycopg2.connect(dsn)

SPORTS_WORDS = {"uga", "georgia", "bulldogs", "football", "cfb", "ncaa", "sec", "college football", "espn"}
FINANCE_WORDS = {"stock", "market", "nasdaq", "dow", "s&p", "sp500", "crypto", "bitcoin", "invest", "fed", "rate", "earnings"}
ATLANTA_WORDS = {"atlanta", "atl", "gwinnett", "fulton", "dekalb", "cobb", "buckhead", "marietta", "decatur"}
SOCCER_WORDS = {"soccer", "mls", "premier league", "fifa", "champions league", "epl", "messi", "ronaldo"}
TECH_WORDS = {"ai", "llm", "openai", "anthropic", "google", "apple", "nvidia", "microsoft", "tech", "startup"}

def _detect_category(query: str):
    q = query.lower()
    if any(w in q for w in SPORTS_WORDS):
        return "uga_football"
    if any(w in q for w in FINANCE_WORDS):
        return "stocks"
    if any(w in q for w in ATLANTA_WORDS):
        return "atlanta_news"
    if any(w in q for w in SOCCER_WORDS):
        return "soccer"
    if any(w in q for w in TECH_WORDS):
        return "tech_ai"
    return None

def get_news_context(query: str, max_items: int = 4, hours_back: int = 48) -> str:
    category = _detect_category(query)
    cutoff = datetime.utcnow() - timedelta(hours=hours_back)
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if category:
            cur.execute("""
                SELECT r.title, ps.summary, fs.category, ps.processed_at
                FROM processed_summaries ps
                JOIN raw_ingest_items r ON r.id = ps.item_id
                JOIN feed_sources fs ON fs.id = r.source_id
                WHERE ps.processed_at >= %s AND fs.category = %s
                ORDER BY ps.processed_at DESC
                LIMIT %s
            """, (cutoff, category, max_items))
        else:
            cur.execute("""
                SELECT r.title, ps.summary, fs.category, ps.processed_at
                FROM processed_summaries ps
                JOIN raw_ingest_items r ON r.id = ps.item_id
                JOIN feed_sources fs ON fs.id = r.source_id
                WHERE ps.processed_at >= %s
                ORDER BY ps.processed_at DESC
                LIMIT %s
            """, (cutoff, max_items))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if not rows:
            return ""
        parts = ["\n\n[JARVIS News Context]"]
        for title, summary, cat, processed_at in rows:
            age_h = int((datetime.utcnow() - processed_at.replace(tzinfo=None)).total_seconds() / 3600)
            parts.append(f"- [{cat} | {age_h}h ago] {title}: {summary}")
        parts.append("[/JARVIS News Context]")
        return "\n".join(parts)
    except Exception as e:
        import logging
        logging.getLogger("context_injector").warning(f"News context lookup failed: {e}")
        return ""
