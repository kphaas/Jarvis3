#!/usr/bin/env python3
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

STAGING = Path.home() / "jarvis_staging"
QUEUE = (STAGING / "publish_queue").resolve()
AUDIT_LOG = STAGING / "logs" / "governance_audit.jsonl"
POLICY_PATH = STAGING / "metadata" / "governance_policy.json"

class GovernanceError(Exception):
    pass

def load_current_policy_version() -> str:
    try:
        raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        return raw.get("policy_version", "unknown")
    except Exception:
        return "unknown"

def audit(event: dict) -> None:
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=True) + "\n")

def canonical(p: Path) -> Path:
    return p.expanduser().resolve()

def load_sidecar(staged: Path) -> dict:
    sidecar = staged.with_suffix(staged.suffix + ".meta.json")
    if not sidecar.exists():
        raise GovernanceError(f"Missing sidecar: {sidecar}")
    return json.loads(sidecar.read_text(encoding="utf-8"))

def load_sidecar_for_staged(staged_path: Path) -> dict:
    sidecar = staged_path.with_suffix(staged_path.suffix + ".meta.json")
    if sidecar.exists():
        return json.loads(sidecar.read_text(encoding="utf-8"))
    return {}

def request_publish(staged_path: str, requested_by: str, note: str = "") -> dict:
    staged = canonical(Path(staged_path))

    classified_root = (STAGING / "classified").resolve()
    if classified_root != staged and classified_root not in staged.parents:
        raise GovernanceError("Staged path must be under ~/jarvis_staging/classified")

    if not staged.exists() or not staged.is_file():
        raise GovernanceError(f"Missing staged file: {staged}")

    meta = load_sidecar(staged)
    classification = meta.get("classification")
    human_reviewed = bool(meta.get("human_reviewed", False))

    if "policy_version" not in meta:
        meta["policy_version"] = load_current_policy_version()
        # Write back into the sidecar so future steps are deterministic
        sidecar_path = staged.with_suffix(staged.suffix + ".meta.json")
        sidecar_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    if classification in ("sensitive", "restricted") and not human_reviewed:
        raise GovernanceError("Cannot request publish unless human_reviewed=true")

    # Ensure queue dirs exist
    for d in ["pending", "approved", "shipped", "rejected", "manifests"]:
        (QUEUE / d).mkdir(parents=True, exist_ok=True)

    # Copy file into pending (preserve normalized filename)
    pending_path = canonical(QUEUE / "pending" / staged.name)
    if pending_path.exists():
        # If already pending, do not overwrite; just reuse
        pass
    else:
        shutil.copy2(staged, pending_path)

    # Manifest name is deterministic and unique-ish
    policy_version = meta.get("policy_version", "unknown")
    manifest_id = f"{staged.stem}__{meta.get('sha256','')[:12]}"
    manifest_path = canonical(QUEUE / "manifests" / f"{manifest_id}.publish.json")

    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        # If still pending, return existing manifest (idempotent)
        if existing.get("status") == "pending":
            return existing
        raise GovernanceError(
            f"Manifest already exists with status={existing.get('status')}: {manifest_path}"
        )

    manifest = {
        "id": manifest_id,
        "policy_version": policy_version,
    "requested_at": datetime.now(timezone.utc).isoformat(),
        "requested_by": requested_by,
        "note": note,
        "classification": classification,
        "sha256": meta.get("sha256", ""),
        "staged_path": str(staged),
        "pending_path": str(pending_path),
        "status": "pending",
        "approved_at": None,
        "approved_by": None,
        "ship_attempts": 0,
        "shipped_at": None,
        "ship_result": None
    }

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    audit({
        "event": "publish_requested",
        "policy_version": policy_version,
    "classification": classification,
        "staged_path": str(staged),
        "pending_path": str(pending_path),
        "manifest": str(manifest_path),
        "requested_by": requested_by,
        "sha256": meta.get("sha256",""),
    })

    return manifest

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("staged_path")
    ap.add_argument("--by", default="jarvis", help="Requester (jarvis or human handle)")
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    out = request_publish(args.staged_path, args.by, args.note)
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
