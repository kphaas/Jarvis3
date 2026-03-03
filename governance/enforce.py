#!/usr/bin/env python3
import json
from dataclasses import dataclass
from pathlib import Path

STAGING = Path.home() / "jarvis_staging"
POLICY_PATH = STAGING / "metadata" / "governance_policy.json"

class GovernanceError(Exception):
    pass

@dataclass(frozen=True)
class GovernanceDecision:
    classification: str
    staged_path: str
    allow_read: bool
    allow_outbound_api: bool
    allow_cache: bool
    requires_acknowledge: bool
    requires_human_reviewed_for_processing: bool

def load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))

def canonicalize_staged_path(path_str: str) -> Path:
    # Resolve symlinks to keep logs consistent
    return Path(path_str).expanduser().resolve()

def load_sidecar(staged_file: Path) -> dict:
    sidecar = staged_file.with_suffix(staged_file.suffix + ".meta.json")
    if not sidecar.exists():
        raise GovernanceError(f"Missing sidecar: {sidecar}")
    return json.loads(sidecar.read_text(encoding="utf-8"))

def decide(staged_path: str, acknowledge: bool = False, allow_outbound_override: bool = False) -> GovernanceDecision:
    p = canonicalize_staged_path(staged_path)

    classified_root = (STAGING / "classified").resolve()
    if classified_root != p and classified_root not in p.parents:
        raise GovernanceError("Path must be under ~/jarvis_staging/classified")

    meta = load_sidecar(p)
    classification = meta.get("classification")
    if classification not in ("public", "sensitive", "restricted"):
        raise GovernanceError("Invalid classification in sidecar")

    policy = load_policy()
    rules = policy["rules"][classification]

    human_reviewed = bool(meta.get("human_reviewed", False))

    # Core rule gates
    if classification in ("sensitive", "restricted") and not human_reviewed:
        # allow read is still ok, but processing features should be blocked by your app
        # We expose this via requires_human_reviewed_for_processing flag.
        pass

    # Restricted acknowledge gate
    if rules["requires_acknowledge"] and not acknowledge:
        raise GovernanceError("Restricted document requires acknowledge=true")

    # Outbound API default
    allow_outbound = bool(rules["outbound_api_allowed"])

    # Your chosen model:
    # - sensitive outbound is blocked by default but can be allowed with explicit override AFTER human_reviewed
    # - restricted outbound never allowed
    if classification == "sensitive":
        if allow_outbound_override and human_reviewed:
            allow_outbound = True
        else:
            allow_outbound = False

    if classification == "restricted":
        allow_outbound = False

    allow_cache = bool(rules["cache_allowed"])

    return GovernanceDecision(
        classification=classification,
        staged_path=str(p),
        allow_read=bool(rules["read_allowed"]),
        allow_outbound_api=allow_outbound,
        allow_cache=allow_cache,
        requires_acknowledge=bool(rules["requires_acknowledge"]),
        requires_human_reviewed_for_processing=bool(rules["requires_human_reviewed_for_processing"]) and not human_reviewed,
    )
