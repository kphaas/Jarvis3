import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import JWTError, jwt

app = FastAPI(title="JARVIS Auth Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

ACCESS_TOKEN_EXPIRE_HOURS = 8
ALGORITHM = "HS256"

ROLE_SCOPES = {
    "ken":     "admin",
    "ryleigh": "child_ryleigh",
    "sloane":  "child_sloane",
    "guest":   "guest",
}


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
        host="localhost", port=5432,
        dbname="jarvis", user="jarvis",
        password=_get_secret("POSTGRES_PASSWORD"),
        connect_timeout=5
    )


def _jwt_secret() -> str:
    s = _get_secret("JARVIS_JWT_SECRET")
    if not s:
        raise RuntimeError("JARVIS_JWT_SECRET not set in .secrets")
    return s


def create_token(user_id: str, role: str) -> dict:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": expires,
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        "user_id": user_id,
        "role": role,
    }


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def _user_exists(user_id: str) -> Optional[dict]:
    try:
        conn = _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT user_id, profile_data FROM user_profile WHERE user_id = %s",
            (user_id,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


class LoginRequest(BaseModel):
    user_id: str
    pin: Optional[str] = None


class ValidateRequest(BaseModel):
    token: str


class RefreshRequest(BaseModel):
    token: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "auth",
        "ts": datetime.now(timezone.utc).isoformat()
    }


@app.post("/v1/auth/login")
def login(req: LoginRequest):
    user_id = req.user_id.lower().strip()
    if user_id not in ROLE_SCOPES:
        raise HTTPException(status_code=401, detail=f"Unknown user: {user_id}")
    user = _user_exists(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found in database")
    role = ROLE_SCOPES[user_id]
    return create_token(user_id, role)


@app.post("/v1/auth/validate")
def validate(req: ValidateRequest):
    payload = decode_token(req.token)
    return {
        "valid": True,
        "user_id": payload["sub"],
        "role": payload["role"],
        "expires": payload["exp"],
    }


@app.post("/v1/auth/refresh")
def refresh(req: RefreshRequest):
    payload = decode_token(req.token)
    user_id = payload["sub"]
    role = payload["role"]
    return create_token(user_id, role)


@app.get("/v1/auth/users")
def list_users():
    try:
        conn = _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT user_id, profile_data, created_at FROM user_profile ORDER BY user_id")
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"users": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/auth/elevate")
def elevate(req: LoginRequest):
    admin_pin = _get_secret("JARVIS_ADMIN_PIN")
    if not admin_pin:
        raise HTTPException(status_code=503, detail="PIN elevation not configured")
    if not req.pin or req.pin != admin_pin:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    return create_token("ken", "admin")


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header required")
    return decode_token(credentials.credentials)
