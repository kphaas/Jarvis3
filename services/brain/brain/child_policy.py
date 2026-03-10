import psycopg2
import os
import logging

log = logging.getLogger("child_policy")

BLOCKED_PATTERNS = [
    "how to make a bomb", "how to make drugs", "how to get high",
    "kill yourself", "suicide", "self harm", "how to hurt",
    "porn", "naked", "sex with", "nude",
    "how to buy alcohol", "how to buy weed", "cocaine", "heroin",
]

RYLEIGH_SYSTEM = """You are JARVIS, a friendly and helpful assistant talking to Ryleigh, an 8-year-old.
Rules you must follow:
- Use simple, clear language appropriate for an 8-year-old
- Be encouraging, positive, and educational
- Never discuss violence, adult content, drugs, alcohol, weapons, or scary topics
- If asked about something inappropriate, say: "That is not something I can help with. Let us find something fun to talk about instead!"
- Keep answers concise and engaging

"""

SLOANE_SYSTEM = """You are JARVIS, a friendly and helpful assistant talking to Sloane, a 5-year-old.
Rules you must follow:
- Use very simple words and very short sentences for a 5-year-old
- Be warm, playful, and encouraging
- Only discuss animals, colors, simple stories, family, games, and fun learning topics
- Never discuss anything scary, violent, or adult
- If asked about something inappropriate, say: "Let us talk about something fun instead!"
- Keep all answers very short

"""

BLOCKED_RESPONSE = "That is not something I can help with. Let us find something fun and interesting to talk about instead!"

def _get_db_connection():
    pw = ""
    secrets_path = os.path.expanduser("~/jarvis/.secrets")
    try:
        with open(secrets_path) as f:
            for line in f:
                if line.startswith("POSTGRES_PASSWORD="):
                    pw = line.strip().split("=", 1)[1]
    except Exception:
        pass
    dsn = f"host=localhost port=5432 dbname=jarvis user=jarvisbrain password={pw}" if pw else "host=localhost port=5432 dbname=jarvis user=jarvisbrain"
    return psycopg2.connect(dsn)

def get_user_profile(username: str) -> dict:
    try:
        conn = _get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT username, display_name, role, age, content_filter_level, blocked_topics, max_complexity FROM user_profiles WHERE username = %s AND active = true",
            (username,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return {"username": username, "role": "unknown", "max_complexity": 10, "blocked_topics": [], "content_filter_level": "none"}
        return {
            "username": row[0], "display_name": row[1], "role": row[2],
            "age": row[3], "content_filter_level": row[4],
            "blocked_topics": row[5] or [], "max_complexity": row[6],
        }
    except Exception as e:
        log.warning(f"Profile lookup failed for {username}: {e}")
        return {"username": username, "role": "unknown", "max_complexity": 10, "blocked_topics": [], "content_filter_level": "none"}

def is_child_role(role: str) -> bool:
    return role in ("child_ryleigh", "child_sloane")

def check_content_safe(message: str, profile: dict) -> tuple[bool, str]:
    if not is_child_role(profile.get("role", "")):
        return True, ""
    msg_lower = message.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in msg_lower:
            return False, f"blocked_pattern:{pattern}"
    for topic in (profile.get("blocked_topics") or []):
        if topic.replace("_", " ") in msg_lower:
            return False, f"blocked_topic:{topic}"
    return True, ""

def build_child_prompt(intent: str, role: str) -> str:
    if role == "child_ryleigh":
        return RYLEIGH_SYSTEM + intent
    if role == "child_sloane":
        return SLOANE_SYSTEM + intent
    return intent

def enforce_complexity(requested: int, profile: dict) -> int:
    return min(requested, profile.get("max_complexity", 10))
