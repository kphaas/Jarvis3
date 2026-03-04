"""
git_client.py — Git operations for JARVIS code writer.
Always commits to a feature branch, never main.

JARVIS-GENERATED: False (human-authored foundation file)
"""
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path.home() / "jarvis"


def _run(cmd: list, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd or REPO_ROOT),
    )


def get_or_create_branch(branch_hint: str) -> dict:
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "-", branch_hint)[:50]
    branch = f"feature/jarvis-{safe}"
    check = _run(["git", "branch", "--list", branch])
    if branch in check.stdout:
        r = _run(["git", "checkout", branch])
    else:
        r = _run(["git", "checkout", "-b", branch])
    if r.returncode != 0:
        return {"ok": False, "error": r.stderr.strip(), "branch": branch}
    return {"ok": True, "branch": branch}


def get_diff(file_path: str) -> str:
    result = _run(["git", "diff", "--cached", file_path])
    return result.stdout.strip() or "(new file)"


def stage_and_commit(file_path: str, message: str) -> dict:
    add = _run(["git", "add", file_path])
    if add.returncode != 0:
        return {"ok": False, "error": add.stderr.strip()}
    diff = get_diff(file_path)
    commit = _run(["git", "commit", "-m", message])
    if commit.returncode != 0:
        add2 = _run(["git", "add", file_path])
        if add2.returncode != 0:
            return {"ok": False, "error": add2.stderr.strip()}
        commit2 = _run(["git", "commit", "-m", message])
        if commit2.returncode != 0:
            return {"ok": False, "error": commit2.stderr.strip()}
    rev = _run(["git", "rev-parse", "--short", "HEAD"])
    return {"ok": True, "commit_hash": rev.stdout.strip(), "diff": diff}


def push_branch(branch: str) -> dict:
    r = _run(["git", "push", "--set-upstream", "origin", branch])
    if r.returncode != 0:
        return {"ok": False, "error": r.stderr.strip()}
    return {"ok": True}


def return_to_main() -> dict:
    r = _run(["git", "checkout", "main"])
    if r.returncode != 0:
        return {"ok": False, "error": r.stderr.strip()}
    return {"ok": True}
