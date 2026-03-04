from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import ipaddress
import hashlib
import socket
import time
import json

import httpx

app = FastAPI(title="Jarvis Gateway")

MAX_BYTES = 3 * 1024 * 1024   # 3 MB
TIMEOUT_S = 10.0
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

class FetchRequest(BaseModel):
    url: str

class FetchResponse(BaseModel):
    url: str
    final_url: Optional[str] = None
    status_code: int
    content_type: Optional[str] = None
    bytes: int
    sha256: str
    text_excerpt: str
    meta: Dict[str, Any] = {}

def _is_private_host(host: str) -> bool:
    # If it's an IP literal, block private/local ranges
    try:
        ip = ipaddress.ip_address(host)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
        )
    except ValueError:
        # Not an IP literal. We still block obvious local names.
        lowered = host.lower()
        if lowered in ("localhost",):
            return True
        if lowered.endswith(".local"):
            return True
        return False

def _host_resolves_to_private(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        # If DNS fails, let httpx handle the error
        return False

    for family, _, _, _, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
            ):
                return True
        except ValueError:
            continue

    return False

def _validate_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http/https URLs are allowed.")
    if not u.netloc:
        raise HTTPException(status_code=400, detail="URL must include a hostname.")
    host = u.hostname or ""
    if _is_private_host(host):
    	_log_event({
        	"ts": time.time(),
        	"blocked": True,
        	"reason": "private_host",
        	"host": host,
        	"url": url,
    	})
    	raise HTTPException(status_code=400, detail="Blocked target host (private/local).")

    if _host_resolves_to_private(host):
    	_log_event({
        	"ts": time.time(),
        	"blocked": True,
        	"reason": "resolves_private",
        	"host": host,
        	"url": url,
    	})
    	raise HTTPException(status_code=400, detail="Blocked target host (resolves to private/local).")

# --- Jarvis auth (Brain -> Gateway) ---
import os
from fastapi import Header

def require_jarvis_token(x_jarvis_token: Optional[str] = Header(default=None)):
    expected = os.environ.get('JARVIS_GATEWAY_TOKEN')
    if not expected:
        raise HTTPException(status_code=500, detail='Gateway misconfigured: missing JARVIS_GATEWAY_TOKEN')
    if not x_jarvis_token or x_jarvis_token != expected:
        raise HTTPException(status_code=401, detail='Unauthorized')

def _log_event(event: dict) -> None:
    # One JSON line per request (easy to grep + parse)
    try:
        print(json.dumps(event, separators=(",", ":"), ensure_ascii=False), flush=True)
    except Exception:
        # Never let logging break the gateway
        pass

@app.get("/health")
def health(_auth=Depends(require_jarvis_token)):
    return {"status": "ok"}

@app.post("/fetch", response_model=FetchResponse)
def fetch(req: FetchRequest, request: Request, _auth=Depends(require_jarvis_token)):
    _validate_url(req.url)
    t0 = time.time()
    client_ip = request.client.host if request.client else None

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=TIMEOUT_S,
            headers={"User-Agent": UA},
        ) as client:
            r = client.get(req.url)
    except httpx.RequestError as e:
        ms = int((time.time() - t0) * 1000)
        _log_event({
            "ts": time.time(),
            "client_ip": client_ip,
            "url": req.url,
            "host": urlparse(req.url).hostname,
            "error": e.__class__.__name__,
            "ms": ms,
        })
        raise HTTPException(status_code=502, detail=f"Fetch failed: {e.__class__.__name__}")

    content = r.content or b""
    content = content[:MAX_BYTES]

    sha = hashlib.sha256(content).hexdigest()
    ct = r.headers.get("content-type")

    # Keep only text-ish outputs
    text = ""
    if ct and ("text/" in ct or "json" in ct or "xml" in ct or "html" in ct):
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            text = ""
    else:
        # Try a gentle decode anyway, but keep it short
        text = content.decode("utf-8", errors="replace")

    excerpt = text.strip().replace("\r", "")
    if len(excerpt) > 8000:
        excerpt = excerpt[:8000] + "\n...[truncated]..."

    ms = int((time.time() - t0) * 1000)

    _log_event({
        "ts": time.time(),
        "client_ip": client_ip,
        "url": req.url,
        "host": urlparse(req.url).hostname,
        "final_url": str(r.url) if r.url else None,
        "redirected": (str(r.url) != req.url) if r.url else False,
        "status": r.status_code,
        "content_type": ct,
        "bytes": len(content),
        "sha256": sha,
        "ms": ms,
    })

    return FetchResponse(
        url=req.url,
        final_url=str(r.url) if r.url else None,
        status_code=r.status_code,
        content_type=ct,
        bytes=len(content),
        sha256=sha,
        text_excerpt=excerpt,
        meta={
            "redirected": str(r.url) != req.url if r.url else False,
    	    "ms": ms,
	},
    )

