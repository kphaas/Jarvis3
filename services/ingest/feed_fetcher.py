import feedparser
import socket
import time
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

log = logging.getLogger("feed_fetcher")

MAX_RETRIES = 3
BACKOFF_BASE = 2
FETCH_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def parse_date(date_str):
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc)
    except Exception:
        return None


def fetch_feed(source_id, url):
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(FETCH_TIMEOUT)
            try:
                feed = feedparser.parse(url, request_headers={"User-Agent": USER_AGENT})
            finally:
                socket.setdefaulttimeout(old_timeout)

            if feed.bozo and not feed.entries:
                raise ValueError(f"Feed parse error: {feed.bozo_exception}")
            entries = []
            for entry in feed.entries:
                content = ""
                if hasattr(entry, "content") and entry.content:
                    content = entry.content[0].get("value", "")
                if not content and hasattr(entry, "summary") and entry.summary:
                    content = entry.summary
                if not content and hasattr(entry, "description") and entry.description:
                    content = entry.description
                if not content and hasattr(entry, "title") and entry.title:
                    content = entry.title
                if not content:
                    continue
                link = getattr(entry, "link", "")
                if not link:
                    continue
                entries.append({
                    "source_id": source_id,
                    "title": getattr(entry, "title", "Untitled")[:500],
                    "url": link,
                    "raw_content": content,
                    "published_at": parse_date(getattr(entry, "published", None)),
                })
            log.info(f"Fetched {len(entries)} entries from {url}")
            return entries
        except Exception as e:
            last_exc = e
            wait = BACKOFF_BASE ** attempt
            log.warning(f"Attempt {attempt+1} failed for {url}: {e} - retrying in {wait}s")
            time.sleep(wait)
    log.error(f"All retries failed for {url}: {last_exc}")
    return []
