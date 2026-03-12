import os
import subprocess
import tempfile
import asyncio
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

BRAIN_URL = "http://100.64.166.22:8182"
AUTH_URL = "http://100.64.166.22:8183"
WHISPER_MODEL = "small"

app = FastAPI(title="JARVIS Voice Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_whisper = None
_token_cache: dict[str, str] = {}

def get_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        _whisper = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _whisper

VOICE_MAP = {
    "ken": "Alex",
    "ryleigh": "Samantha",
    "sloane": "Victoria",
    "guest": "Samantha",
}

async def _fetch_token(user_id: str) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{AUTH_URL}/v1/auth/login", json={"user_id": user_id})
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail=f"auth failed for {user_id}")
        return r.json()["access_token"]

async def _get_token(user_id: str) -> str:
    if user_id not in _token_cache:
        _token_cache[user_id] = await _fetch_token(user_id)
    return _token_cache[user_id]

@app.get("/", response_class=HTMLResponse)
async def ui():
    p = Path(__file__).parent / "ui.html"
    return HTMLResponse(p.read_text())

@app.get("/v1/voice/status")
def status():
    whisper_ok = False
    try:
        get_whisper()
        whisper_ok = True
    except Exception:
        pass
    tts_ok = subprocess.run(["which", "say"], capture_output=True).returncode == 0
    ffmpeg_ok = subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0
    return {
        "whisper": whisper_ok,
        "whisper_model": WHISPER_MODEL,
        "tts": tts_ok,
        "tts_backend": "macos_say",
        "ffmpeg": ffmpeg_ok,
        "status": "ok" if (whisper_ok and tts_ok) else "degraded",
    }

@app.post("/v1/voice/auth")
async def voice_auth(request: Request):
    body = await request.json()
    user_id = body.get("user_id", "").lower()
    pin = body.get("pin")

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    if user_id == "ken":
        if not pin:
            raise HTTPException(status_code=400, detail="PIN required for ken")
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{AUTH_URL}/v1/auth/elevate", json={"user_id": "ken", "pin": pin})
            if r.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid PIN")
            token = r.json()["access_token"]
    else:
        token = await _fetch_token(user_id)

    _token_cache[user_id] = token
    return {"status": "ok", "user_id": user_id}

@app.post("/v1/voice/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    data = await audio.read()
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    wav_path = tmp_path.replace(".webm", ".wav")
    try:
        import subprocess
        result = subprocess.run(["/opt/homebrew/bin/ffmpeg", "-y", "-i", tmp_path, "-ar", "16000", "-ac", "1", wav_path],
            capture_output=True)
        import os, sys
        print(f"FFMPEG rc={result.returncode} webm_size={os.path.getsize(tmp_path)} stderr={result.stderr[-200:].decode()}", file=sys.stderr, flush=True)
        model = get_whisper()
        import shutil; shutil.copy(wav_path, "/tmp/jarvis_last.wav")
        segments, info = model.transcribe(wav_path, beam_size=5, language="en", vad_filter=True, condition_on_previous_text=False)
        text = " ".join(s.text.strip() for s in segments).strip()
        return {"text": text, "language": info.language}
    except Exception as e:
        print(f"[VOICE] Avatar Exception: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        try:
            os.unlink(wav_path)
        except Exception:
            pass

@app.post("/v1/voice/speak")
async def speak(request: Request):
    body = await request.json()
    text = body.get("text", "").strip()
    user = body.get("user", "ken").lower()
    voice = body.get("voice")
    speed = body.get("speed", 1.0)
    
    if not text:
        raise HTTPException(status_code=400, detail="no text")
    
    AVATAR_URL = "http://100.87.223.31:4002"
    import sys
    try:
        print(f"[VOICE] Attempting Avatar TTS: user={user}, voice={voice}, speed={speed}", file=sys.stderr, flush=True)
        async with httpx.AsyncClient(timeout=30) as client:
            payload = {
                "text": text,
                "user_id": user,
                "speed": speed,
                "play_local": False
            }
            if voice:
                payload["voice"] = voice
            
            resp = await client.post(
                f"{AVATAR_URL}/v1/avatar/speak/stream",
                json=payload
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="Avatar TTS failed")
            
            wav_bytes = resp.content
            tmp_path = f"/tmp/jarvis_tts_{user}.wav"
            with open(tmp_path, "wb") as f:
                f.write(wav_bytes)
            
            subprocess.Popen(
                ["afplay", tmp_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            return {
                "status": "ok",
                "voice": resp.headers.get("X-Voice", "unknown"),
                "chars": len(text),
                "backend": "kokoro-avatar"
            }
    except httpx.ConnectError as ce:
        print(f"[VOICE] Avatar ConnectError: {ce}, falling back to macOS say", file=sys.stderr, flush=True)
        voice_fallback = VOICE_MAP.get(user, "Alex")
        subprocess.run(["say", "-v", voice_fallback, text], timeout=120, check=True)
        return {
            "status": "ok",
            "voice": voice_fallback,
            "chars": len(text),
            "backend": "macos-say-fallback"
        }
    except Exception as e:
        print(f"[VOICE] Avatar Exception: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/voice/ask")
async def ask_brain(request: Request):
    body = await request.json()
    user_id = body.get("user", "ken").lower()
    t0 = time.time()

    token = await _get_token(user_id)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(f"{BRAIN_URL}/v1/ask", json=body, headers=headers)
            if resp.status_code == 401:
                _token_cache.pop(user_id, None)
                token = await _get_token(user_id)
                headers["Authorization"] = f"Bearer {token}"
                resp = await client.post(f"{BRAIN_URL}/v1/ask", json=body, headers=headers)
            data = resp.json()
            data["latency_ms"] = int((time.time() - t0) * 1000)
            return data
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="brain unreachable")
    except Exception as e:
        print(f"[VOICE] Avatar Exception: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/voice/brain-health")
async def brain_health():
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            r = await client.get(f"{BRAIN_URL}/health")
            return {"ok": r.status_code == 200}
    except Exception:
        return {"ok": False}

@app.get("/health")
def health():
    return {"status": "ok", "service": "voice"}

@app.get("/v1/metrics")
def metrics():
    import psutil
    return {
        "cpu_pct": psutil.cpu_percent(interval=0.1),
        "ram_pct": psutil.virtual_memory().percent,
        "ram_used_gb": round(psutil.virtual_memory().used / 1e9, 2),
        "ram_total_gb": round(psutil.virtual_memory().total / 1e9, 2),
        "disk_pct": psutil.disk_usage("/").percent,
        "disk_used_gb": round(psutil.disk_usage("/").used / 1e9, 2),
        "disk_total_gb": round(psutil.disk_usage("/").total / 1e9, 2),
        "load_avg": " ".join(str(round(x, 2)) for x in psutil.getloadavg()),
        "process_count": len(psutil.pids()),
    }

@app.get("/v1/local/health")
def local_health():
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        return {"ollama": "ok", "ollama_running": True, "models": models, "model_count": len(models)}
    except Exception:
        return {"ollama": "unreachable", "ollama_running": False, "models": [], "model_count": 0}
