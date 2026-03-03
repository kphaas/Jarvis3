#!/usr/bin/env python3
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

STAGING = Path.home() / "jarvis_staging"
QUEUE = (STAGING / "publish_queue").resolve()
AUDIT_LOG = STAGING / "logs" / "governance_audit.jsonl"

class GovernanceError(Exception):
    pass

def load_policy_version_from_manifest(manifest: dict) -> str:
    return manifest.get("policy_version", "unknown")

def audit(event: dict) -> None:
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=True) + "\n")

def approve_manifest(manifest_path: str, approved_by: str) -> dict:
    mpath = Path(manifest_path).expanduser().resolve()
    if not mpath.exists():
        raise GovernanceError(f"Missing manifest: {mpath}")

    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    status = manifest.get("status")

    # Idempotency: if already approved or shipped, return as-is (no changes, no audit)
    if status in ("approved", "shipped"):
        return manifest

    if status != "pending":
        raise GovernanceError(f"Manifest not pending: {status}")

    pending_path = Path(manifest["pending_path"]).expanduser().resolve()
    if not pending_path.exists():
        raise GovernanceError(f"Missing pending file: {pending_path}")

    approved_path = (QUEUE / "approved" / pending_path.name).resolve()
    (QUEUE / "approved").mkdir(parents=True, exist_ok=True)

    policy_version = load_policy_version_from_manifest(manifest)

    # Move file into approved
    shutil.move(str(pending_path), approved_path)

    # Update manifest
    manifest["status"] = "approved"
    manifest["approved_at"] = datetime.now(timezone.utc).isoformat()
    manifest["approved_by"] = approved_by
    manifest["approved_path"] = str(approved_path)
    manifest["policy_version"] = policy_version

    mpath.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    audit({
        "event": "publish_approved",
    "policy_version": policy_version,
        "classification": manifest.get("classification"),
        "manifest": str(mpath),
        "approved_by": approved_by,
        "approved_path": str(approved_path),
        "sha256": manifest.get("sha256",""),
    })

    return manifest

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest_path")
    ap.add_argument("--by", default="ken")
    args = ap.parse_args()
    out = approve_manifest(args.manifest_path, args.by)
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
