#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

STAGING = Path.home() / "jarvis_staging"
AUDIT_LOG = STAGING / "logs" / "governance_audit.jsonl"

class GovernanceError(Exception):
    pass

def audit(event: dict) -> None:
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=True) + "\n")

def approve(staged_path: str, reviewer: str, note: str = "") -> dict:
    p = Path(staged_path).expanduser().resolve()
    classified_root = (STAGING / "classified").resolve()

    if classified_root != p and classified_root not in p.parents:
        raise GovernanceError("Path must be under ~/jarvis_staging/classified")

    meta_path = p.with_suffix(p.suffix + ".meta.json")
    if not meta_path.exists():
        raise GovernanceError(f"Missing sidecar: {meta_path}")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    classification = meta.get("classification")
    if classification not in ("public", "sensitive", "restricted"):
        raise GovernanceError("Invalid classification in meta")

    # Only meaningful for sensitive/restricted, but safe for public
    meta["human_reviewed"] = True
    meta["human_reviewed_at"] = datetime.now().isoformat()
    meta["human_reviewed_by"] = reviewer
    if note:
        meta["human_review_note"] = note

    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    audit({
        "event": "human_approve",
        "classification": classification,
        "staged_path": str(p),
        "reviewer": reviewer,
        "note": note,
        "sha256": meta.get("sha256", ""),
    })

    return meta

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("staged_path", help="Path to staged file under ~/jarvis_staging/classified/<level>/...")
    ap.add_argument("--reviewer", default="ken", help="Reviewer name/handle")
    ap.add_argument("--note", default="", help="Optional note")
    args = ap.parse_args()

    meta = approve(args.staged_path, args.reviewer, args.note)
    print(json.dumps(meta, indent=2))

if __name__ == "__main__":
    main()
