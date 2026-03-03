#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

STAGING = Path.home() / "jarvis_staging"
QUEUE = (STAGING / "publish_queue").resolve()
AUDIT_LOG = STAGING / "logs" / "governance_audit.jsonl"
POLICY_PATH = STAGING / "metadata" / "governance_policy.json"

class GovernanceError(Exception):
    pass

def canonical(p: Path) -> Path:
    return p.expanduser().resolve()

def audit(event: dict) -> None:
    event["ts"] = datetime.now(timezone.utc).isoformat()
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=True) + "\n")

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_policy() -> dict:
    if not POLICY_PATH.exists():
        raise GovernanceError(f"Missing policy file: {POLICY_PATH}")
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))

def publish_dest_path(publish_root: Path, classification: str, approved_path: Path) -> Path:
    # Deterministic foldering:
    # layout = "classification/YYYY/MM" -> <root>/<classification>/<YYYY>/<MM>/<filename>
    # layout = "classification"         -> <root>/<classification>/<filename>
    date_prefix = approved_path.name[:10]  # expects "YYYY-MM-DD" at start
    yyyy = date_prefix[0:4] if len(date_prefix) >= 4 else "unknown"
    mm = date_prefix[5:7] if len(date_prefix) >= 7 else "unknown"

    policy = load_policy()
    publish_cfg = policy.get("publish", {})
    layout = publish_cfg.get("folder_layout", "classification")

    if layout == "classification/YYYY/MM":
        return canonical(publish_root / classification / yyyy / mm / approved_path.name)

    # default
    return canonical(publish_root / classification / approved_path.name)

def atomic_copy2(src: Path, dest: Path) -> None:
    # Copy to temp then rename for safety on SMB
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + f".tmp.{os.getpid()}")
    shutil.copy2(src, tmp)
    os.replace(tmp, dest)

def ship_manifest(manifest_path: str, shipped_by: str, mode: str = "local") -> dict:
    mpath = canonical(Path(manifest_path))
    if not mpath.exists():
        raise GovernanceError(f"Missing manifest: {mpath}")

    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    status = manifest.get("status")

    # Idempotency: if already shipped, return as-is (no changes, no audit)
    if status == "shipped":
        return manifest

    if status != "approved":
        raise GovernanceError(f"Manifest not approved: {status}")

    approved_path = canonical(Path(manifest.get("approved_path", "")))
    if not approved_path.exists():
        raise GovernanceError(f"Missing approved file: {approved_path}")

    classification = manifest.get("classification", "unknown")
    policy_version = manifest.get("policy_version", "unknown")
    sha = manifest.get("sha256", "")

    (QUEUE / "shipped").mkdir(parents=True, exist_ok=True)
    shipped_path = canonical(QUEUE / "shipped" / approved_path.name)

    published_path = None
    result = ""

    if mode == "local":
        shutil.move(str(approved_path), shipped_path)
        result = f"moved to {shipped_path}"

    elif mode == "unraid":
        # Safety rule: default deny restricted -> Unraid publish
        if classification == "restricted":
            raise GovernanceError("Refusing to publish restricted content to Unraid (default deny).")

        policy = load_policy()
        publish_root = canonical(Path(policy.get("publish_root_ro", "")).expanduser())
        if not publish_root.exists():
            raise GovernanceError(f"Publish root does not exist: {publish_root}")

        publish_cfg = policy.get("publish", {})
        allowed_roots = [canonical(Path(p)) for p in publish_cfg.get("allowed_publish_roots", [])]
        if not allowed_roots:
            raise GovernanceError("No allowed_publish_roots configured in policy (publish.allowed_publish_roots)")

        if publish_root not in allowed_roots:
            raise GovernanceError(f"Publish root not allowed: {publish_root} (allowed: {', '.join(map(str, allowed_roots))})")

        deny_list = set(publish_cfg.get("deny_to_unraid", ["restricted"]))
        if classification in deny_list:
            raise GovernanceError(f"Refusing to publish {classification} content to Unraid (policy deny_to_unraid).")
        # Hard allowlist: publish root must be exactly this path
        ALLOWED_PUBLISH_ROOT = canonical(Path("/Volumes/Documents/Jarvis_Published"))
        if publish_root != ALLOWED_PUBLISH_ROOT:
            raise GovernanceError(f"Publish root not allowed: {publish_root} (expected {ALLOWED_PUBLISH_ROOT})")
        if not publish_root.exists():
            raise GovernanceError(f"Publish root does not exist: {publish_root}")

        dest = publish_dest_path(publish_root, classification, approved_path)

        # Idempotent copy: if dest exists and sha matches, skip copy
        if dest.exists() and dest.is_file() and sha:
            dest_sha = sha256_file(dest)
            if dest_sha == sha:
                result = f"already present at {dest} (sha match)"
            else:
                atomic_copy2(approved_path, dest)
                result = f"replaced at {dest} (sha differed)"
        else:
            atomic_copy2(approved_path, dest)
            result = f"copied to {dest}"

        published_path = str(dest)

        # Always finish the local pipeline
        shutil.move(str(approved_path), shipped_path)
        result = result + f"; and moved to {shipped_path}"

    else:
        raise GovernanceError("Unsupported mode. Use --mode local or --mode unraid.")

    manifest["status"] = "shipped"
    manifest["shipped_at"] = datetime.now(timezone.utc).isoformat()
    manifest["shipped_by"] = shipped_by
    manifest["ship_attempts"] = int(manifest.get("ship_attempts", 0)) + 1
    manifest["ship_result"] = result
    manifest["shipped_path"] = str(shipped_path)
    manifest["policy_version"] = policy_version
    if published_path:
        manifest["published_path"] = published_path

    mpath.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    audit({
        "event": "publish_shipped",
        "policy_version": policy_version,
        "classification": classification,
        "manifest": str(mpath),
        "shipped_by": shipped_by,
        "shipped_path": str(shipped_path),
        "published_path": published_path,
        "sha256": sha,
        "mode": mode,
    })

    return manifest

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest_path")
    ap.add_argument("--by", default="jarvis")
    ap.add_argument("--mode", default="local", choices=["local", "unraid"])
    args = ap.parse_args()

    out = ship_manifest(args.manifest_path, args.by, args.mode)
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
