import os
import io
import json
import base64
import asyncio
import subprocess
import psycopg2
import psycopg2.extras
import soundfile as sf
import numpy as np
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from kokoro_onnx import Kokoro

app = FastAPI(title="JARVIS Avatar Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_DIR = Path(__file__).parent
KOKORO_MODEL = str(MODEL_DIR / "kokoro-v1.0.onnx")
VOICES_FILE  = str(MODEL_DIR / "voices-v1.0.bin")

DEFAULT_VOICES = {
    "ken":     "bf_emma",
    "ken_clone": "xtts_ken",
    "ryleigh": "af_sarah",
    "sloane":  "af_sky",
    "guest":   "bf_alice",
}

VOICE_DESCRIPTIONS = {
    "xtts_ken": "Ken voice clone (XTTS v2)",
    "bf_alice":    "British Female \u2014 Alice",
    "bf_emma":     "British Female \u2014 Emma",
    "bf_isabella": "British Female \u2014 Isabella",
    "bf_lily":     "British Female \u2014 Lily",
    "bm_daniel":   "British Male \u2014 Daniel",
    "bm_george":   "British Male \u2014 George",
    "af_sarah":    "American Female \u2014 Sarah",
    "af_sky":      "American Female \u2014 Sky",
    "af_nova":     "American Female \u2014 Nova",
    "af_bella":    "American Female \u2014 Bella",
    "af_heart":    "American Female \u2014 Heart",
    "am_adam":     "American Male \u2014 Adam",
    "am_michael":  "American Male \u2014 Michael",
    "am_echo":     "American Male \u2014 Echo",
}

_kokoro: Optional[Kokoro] = None


def _get_kokoro() -> Kokoro:
    global _kokoro
    if _kokoro is None:
        _kokoro = Kokoro(KOKORO_MODEL, VOICES_FILE)
    return _kokoro


def _get_secret(key: str) -> str:
    secrets_path = os.path.expanduser("~/jarvis/.secrets")
    try:
        with open(secrets_path) as f:
            for line in f:
                if line.startswith(f"{key}="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return ""


def _get_conn():
    return psycopg2.connect(
        host="100.64.166.22", port=5432,
        dbname="jarvis", user="jarvis",
        password=_get_secret("POSTGRES_PASSWORD"),
        connect_timeout=5
    )


def _get_user_voice(user_id: str) -> str:
    try:
        conn = _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT profile_data FROM user_profile WHERE user_id = %s",
            (user_id,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row["profile_data"]:
            data = row["profile_data"]
            if isinstance(data, str):
                data = json.loads(data)
            return data.get("avatar_voice", DEFAULT_VOICES.get(user_id, "bf_emma"))
    except Exception:
        pass
    return DEFAULT_VOICES.get(user_id, "bf_emma")


def _set_user_voice(user_id: str, voice: str) -> bool:
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            """UPDATE user_profile
               SET profile_data = profile_data || %s::jsonb,
                   updated_at = NOW()
               WHERE user_id = %s""",
            (json.dumps({"avatar_voice": voice}), user_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception:
        return False


XTTS_URL = "http://localhost:4003"

def _synth_xtts(text: str) -> bytes:
    """Call XTTS voice clone service for Ken. Returns WAV bytes."""
    import httpx
    resp = httpx.post(
        f"{XTTS_URL}/v1/xtts/speak",
        json={"text": text, "user": "ken"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.content


def _synth(text: str, voice: str, speed: float = 1.0) -> bytes:
    """
    Synthesize speech. Routes to XTTS voice clone service if voice='xtts_ken',
    otherwise uses Kokoro TTS for all other voice strings.
    """
    if voice == "xtts_ken":
        try:
            return _synth_xtts(text)
        except Exception as e:
            print(f"[AvatarService] XTTS failed, falling back to Kokoro bf_emma: {e}")
            voice = "bf_emma"
    kokoro = _get_kokoro()
    samples, sample_rate = kokoro.create(text, voice=voice, speed=speed)
    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format="WAV")
    buf.seek(0)
    return buf.read()


class SpeakRequest(BaseModel):
    text: str
    user_id: str = "ken"
    voice: Optional[str] = None
    speed: float = 1.0
    play_local: bool = True


class SetVoiceRequest(BaseModel):
    user_id: str
    voice: str


@app.on_event("startup")
async def startup():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _get_kokoro)
    print("[AvatarService] Kokoro TTS loaded")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "avatar",
        "tts_engine": "kokoro-onnx",
        "model": "kokoro-v1.0",
        "ts": datetime.now(timezone.utc).isoformat()
    }


@app.get("/v1/avatar/voices")
def list_voices():
    kokoro = _get_kokoro()
    all_voices = sorted(kokoro.get_voices()) + ["xtts_ken"]
    return {
        "voices": all_voices,
        "descriptions": VOICE_DESCRIPTIONS,
        "defaults": DEFAULT_VOICES,
    }


@app.get("/v1/avatar/voice/{user_id}")
def get_voice(user_id: str):
    voice = _get_user_voice(user_id)
    return {
        "user_id": user_id,
        "voice": voice,
        "description": VOICE_DESCRIPTIONS.get(voice, voice),
    }


@app.post("/v1/avatar/voice")
def set_voice(req: SetVoiceRequest):
    kokoro = _get_kokoro()
    available = kokoro.get_voices()
    if req.voice not in available:
        raise HTTPException(status_code=400, detail=f"Unknown voice: {req.voice}")
    ok = _set_user_voice(req.user_id, req.voice)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save voice preference")
    return {
        "status": "ok",
        "user_id": req.user_id,
        "voice": req.voice,
        "description": VOICE_DESCRIPTIONS.get(req.voice, req.voice),
    }


@app.post("/v1/avatar/speak")
async def speak(req: SpeakRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")
    voice = req.voice or _get_user_voice(req.user_id)
    loop = asyncio.get_event_loop()
    try:
        wav_bytes = await loop.run_in_executor(
            None, lambda: _synth(req.text, voice, req.speed)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")
    if req.play_local:
        tmp = f"/tmp/jarvis_avatar_{req.user_id}.wav"
        with open(tmp, "wb") as f:
            f.write(wav_bytes)
        subprocess.Popen(
            ["afplay", tmp],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    audio_b64 = base64.b64encode(wav_bytes).decode()
    return {
        "status": "ok",
        "user_id": req.user_id,
        "voice": voice,
        "chars": len(req.text),
        "audio_b64": audio_b64,
        "description": VOICE_DESCRIPTIONS.get(voice, voice),
    }


@app.post("/v1/avatar/speak/stream")
async def speak_stream(req: SpeakRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")
    voice = req.voice or _get_user_voice(req.user_id)
    loop = asyncio.get_event_loop()
    try:
        wav_bytes = await loop.run_in_executor(
            None, lambda: _synth(req.text, voice, req.speed)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")
    return StreamingResponse(
        io.BytesIO(wav_bytes),
        media_type="audio/wav",
        headers={"X-Voice": voice, "X-User": req.user_id}
    )


@app.get("/", response_class=HTMLResponse)
async def ui():
    p = Path(__file__).parent / "avatar_ui.html"
    if p.exists():
        return HTMLResponse(p.read_text())
    return HTMLResponse("<h1>Avatar UI not found</h1>")

@app.get("/monitor", response_class=HTMLResponse)
async def monitor_ui():
    p = Path(__file__).parent / "agent_monitor.html"
    if p.exists():
        return HTMLResponse(p.read_text())
    return HTMLResponse("<h1>Monitor not found</h1>")
