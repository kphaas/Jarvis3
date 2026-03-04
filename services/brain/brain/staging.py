"""
staging.py — Manages the staging area for generated code.
All generated code lands here before promotion to target path.

JARVIS-GENERATED: False (human-authored foundation file)
"""
import os
import shutil
import subprocess
from pathlib import Path

STAGING_DIR = Path.home() / "jarvis_staging"
STAGING_DIR.mkdir(exist_ok=True, mode=0o700)

ALLOWED_WRITE_PATHS = [
    Path.home() / "jarvis" / "services" / "brain" / "brain",
    Path.home() / "jarvis" / "services" / "gateway" / "app",
    Path.home() / "jarvis_staging",
]


def is_allowed_path(target: str) -> bool:
    resolved = Path(target).expanduser().resolve()
    return any(
        str(resolved).startswith(str(p.resolve()))
        for p in ALLOWED_WRITE_PATHS
    )


def write_staged(filename: str, content: str) -> Path:
    staged_path = STAGING_DIR / filename
    staged_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path.write_text(content, encoding="utf-8")
    os.chmod(staged_path, 0o600)
    return staged_path


def validate_syntax(staged_path: Path) -> dict:
    if not str(staged_path).endswith(".py"):
        return {"ok": True, "error": None}
    result = subprocess.run(
        ["python3", "-m", "py_compile", str(staged_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return {"ok": True, "error": None}
    return {"ok": False, "error": result.stderr.strip()}


def validate_lint(staged_path: Path) -> dict:
    if not str(staged_path).endswith(".py"):
        return {"ok": True, "error": None}
    result = subprocess.run(
        ["ruff", "check", str(staged_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return {"ok": True, "error": None}
    return {"ok": False, "error": result.stdout.strip()}


def validate_security(staged_path: Path) -> dict:
    if not str(staged_path).endswith(".py"):
        return {"ok": True, "error": None}
    result = subprocess.run(
        ["bandit", "-r", str(staged_path), "-ll", "-q"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return {"ok": True, "error": None}
    return {"ok": False, "error": result.stdout.strip()}


def format_code(staged_path: Path) -> dict:
    if not str(staged_path).endswith(".py"):
        return {"ok": True, "error": None}
    result = subprocess.run(
        ["black", str(staged_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return {"ok": True, "error": None}
    return {"ok": False, "error": result.stderr.strip()}


def promote(staged_path: Path, target_path: str) -> Path:
    dest = Path(target_path).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(staged_path, dest)
    return dest


def cleanup(staged_path: Path):
    try:
        staged_path.unlink(missing_ok=True)
    except Exception:
        pass
