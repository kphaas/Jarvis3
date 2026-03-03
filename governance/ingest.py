#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

STAGING = Path.home() / "jarvis_staging"
POLICY_PATH = STAGING / "metadata" / "governance_policy.json"
AUDIT_LOG = STAGING / "logs" / "governance_audit.jsonl"

ASCII_SAFE = re.compile(r"[^A-Za-z0-9._-]+")

class GovernanceError(Exception):
    pass

@dataclass(frozen=True)
class Policy:
    policy_version: str
    source_root_ro: Path
    publish_root_ro: Path
    classification_map: dict
    rules: dict

def load_policy() -> Policy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return Policy(
        policy_version=raw.get("policy_version", "unknown"),
        source_root_ro=Path(raw["source_root_ro"]).expanduser().resolve(),
        publish_root_ro=Path(raw.get("publish_root_ro", raw.get("publish", {}).get("allowed_publish_roots", [""])[0] or "")).expanduser().resolve(),
        classification_map=raw["classification_map"],
        rules=raw["rules"],
    )

def audit(event: dict) -> None:
    from datetime import timezone
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

def normalize_component(s: str) -> str:
    s = s.strip().replace(" ", "_")
    s = ASCII_SAFE.sub("_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "untitled"

def normalize_filename(date_str: str, source: str, title: str, version: int, ext: str) -> str:
    source_n = normalize_component(source)
    title_n = normalize_component(title)
    return f"{date_str}__{source_n}__{title_n}__v{version}{ext}"

def resolve_under_root(root: Path, input_path: str) -> Path:
    p = Path(input_path).expanduser().resolve()
    if p != root and root not in p.parents:
        raise GovernanceError(f"Path outside allowed root: {p}")
    return p

def classify_by_top_folder(policy: Policy, abs_path: Path) -> dict:
    rel = abs_path.relative_to(policy.source_root_ro)
    if len(rel.parts) < 2:
        raise GovernanceError("Expected file under a top-level folder like 30_FINANCE/...")

    top = rel.parts[0]
    if top not in policy.classification_map:
        raise GovernanceError(f"Top folder not in classification_map: {top}")

    classification = policy.classification_map[top]
    if classification not in ("public", "sensitive", "restricted"):
        raise GovernanceError(f"Invalid classification value: {classification}")

    return {"classification": classification, "top_folder": top, "relative_path": str(rel)}

def ensure_staging_ready() -> None:
    needed = [
        STAGING / "inbox",
        STAGING / "normalized",
        STAGING / "classified" / "public",
        STAGING / "classified" / "sensitive",
        STAGING / "classified" / "restricted",
        STAGING / "metadata",
        STAGING / "logs",
        STAGING / "tmp",
    ]
    for d in needed:
        d.mkdir(parents=True, exist_ok=True)

def ingest(source_path: str, source_label: str, version: int) -> dict:
    ensure_staging_ready()
    policy = load_policy()

    # Resolve and enforce root containment
    abs_src = resolve_under_root(policy.source_root_ro, source_path)

    if not abs_src.is_file():
        raise GovernanceError(f"Not a file: {abs_src}")

    # Classify deterministically from top folder
    cinfo = classify_by_top_folder(policy, abs_src)
    classification = cinfo["classification"]

    # Copy to inbox (original name)
    inbox_copy = STAGING / "inbox" / abs_src.name
    shutil.copy2(abs_src, inbox_copy)

    # Normalize into normalized/
    date_str = datetime.now().strftime("%Y-%m-%d")
    ext = inbox_copy.suffix
    title = inbox_copy.stem
    norm_name = normalize_filename(date_str, source_label, title, version, ext)

    normalized_path = STAGING / "normalized" / norm_name

    # Handle name collisions deterministically
    if normalized_path.exists():
        # bump version until unused
        v = version
        while normalized_path.exists():
            v += 1
            norm_name = normalize_filename(date_str, source_label, title, v, ext)
            normalized_path = STAGING / "normalized" / norm_name

    shutil.move(str(inbox_copy), normalized_path)

    # Hash after normalization (this is the canonical staged content)
    digest = sha256_file(normalized_path)

    # Copy into classified folder (final staged path)
    staged_path = STAGING / "classified" / classification / norm_name
    shutil.copy2(normalized_path, staged_path)
    staged_path_resolved = staged_path.resolve()

    # Sidecar metadata
    rules = policy.rules[classification]
    meta = {
    "policy_version": policy.policy_version,        
    "classification": classification,
        "top_folder": cinfo["top_folder"],
        "original_source_path": str(abs_src),
        "original_relative_path": cinfo["relative_path"],
        "staged_path": str(staged_path_resolved),
        "ingested_at_local": datetime.now().isoformat(),
        "sha256": digest,
        "normalized": True,
        "human_reviewed": False if classification in ("sensitive", "restricted") else True,
        "rules": {
            "requires_acknowledge": bool(rules["requires_acknowledge"]),
            "outbound_api_allowed": bool(rules["outbound_api_allowed"]),
            "cache_allowed": bool(rules["cache_allowed"]),
            "requires_human_reviewed_for_processing": bool(rules["requires_human_reviewed_for_processing"]),
        },
    }

    sidecar = staged_path.with_suffix(staged_path.suffix + ".meta.json")
    sidecar.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Audit event
    audit({
        "event": "ingest",
    "policy_version": policy.policy_version,        
    "classification": classification,
        "source_path": str(abs_src),
        "staged_path": str(staged_path_resolved),
        "sha256": digest,
        "human_reviewed": meta["human_reviewed"],
    })

    return meta

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="Absolute path under /Volumes/Documents to ingest")
    ap.add_argument("--source", default="Unraid", help="Source label in normalized name")
    ap.add_argument("--version", type=int, default=1, help="Initial version number")
    args = ap.parse_args()

    out = ingest(args.path, args.source, args.version)
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
