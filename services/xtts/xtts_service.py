"""
JARVIS XTTS Voice Clone Service
Endpoint :4003
Serves Ken's voice clone via Coqui XTTS v2.
Other users fall back to Kokoro TTS at :4002.
"""

import io
import os
import logging
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("xtts_service")

# --- Config ---
REFERENCE_WAV = Path(__file__).parent / "voice_samples" / "ken_reference_normalized.wav"
MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

app = FastAPI(title="JARVIS XTTS Voice Clone Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Lazy model loader (loads once on first request) ---
_tts = None

def get_tts():
    global _tts
    if _tts is None:
        logger.info("Loading XTTS v2 model...")
        from TTS.api import TTS
        _tts = TTS(model_name=MODEL_NAME)
        logger.info("XTTS v2 model loaded")
    return _tts


# --- Request schema ---
class SpeakRequest(BaseModel):
    text: str
    user: str = "ken"
    language: str = "en"


# --- Routes ---

@app.get("/health")
def health():
    """Health check — does not load the model."""
    return {"status": "ok", "service": "xtts", "reference_wav": str(REFERENCE_WAV)}


@app.get("/ready")
def ready():
    """Readiness check — confirms model is loaded."""
    loaded = _tts is not None
    return {"ready": loaded, "model": MODEL_NAME}


@app.post("/v1/xtts/speak")
async def speak(req: SpeakRequest):
    """
    Synthesize text using Ken's voice clone.
    Returns WAV audio bytes as a streaming response.
    Only used for user=ken; other users should call avatar service :4002.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    if not REFERENCE_WAV.exists():
        raise HTTPException(status_code=500, detail=f"Reference WAV not found: {REFERENCE_WAV}")

    try:
        tts = get_tts()

        # Synthesize to numpy array
        wav = tts.tts(
            text=req.text,
            speaker_wav=str(REFERENCE_WAV),
            language=req.language,
        )

        # Convert to WAV bytes
        buf = io.BytesIO()
        sf.write(buf, np.array(wav), samplerate=24000, format="WAV")
        buf.seek(0)

        logger.info(f"Synthesized {len(req.text)} chars for user={req.user}")
        return StreamingResponse(buf, media_type="audio/wav")

    except Exception as e:
        logger.error(f"Synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/xtts/warmup")
async def warmup():
    """
    Pre-loads the model into memory.
    Call this after service start to avoid cold-start latency on first request.
    """
    try:
        get_tts()
        return {"status": "ok", "message": "model loaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
