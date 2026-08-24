"""Aggregate predicates for installed independent hardware-profile evidence."""

from __future__ import annotations

import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "fam.product.installed-hardware-matrix/v1alpha1"


def initial_document(run_id: str, candidate: Any) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "run_id": run_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "host": {
            "hostname": platform.node(), "machine": platform.machine(),
            "kernel": platform.release(), "uid": os.geteuid(),
        },
        "candidate": {
            "release_id": candidate.manifest.release_id,
            "signer_key_id": candidate.key_id,
            "component_count": len(candidate.manifest.components),
            "manifest_sha256": candidate.manifest_sha256,
            "wheel_sha256": candidate.wheel_sha256,
        },
        "profiles": {},
        "owner_model_quiescence": None,
        "full_strong_escalation": None,
        "complete_removal": False,
        "live_owner_service_preserved": False,
        "managed_service_inactive": False,
        "passed": False,
    }


def finalize(document: dict[str, object]) -> None:
    profiles = document.get("profiles")
    strong = document.get("full_strong_escalation")
    quiescence = document.get("owner_model_quiescence")
    document["passed"] = bool(
        isinstance(profiles, dict)
        and set(profiles) == {"compat-cpu-16gb", "full-reference-workstation"}
        and all(
            isinstance(value, dict) and value.get("passed") is True
            for value in profiles.values()
        )
        and isinstance(strong, dict)
        and strong.get("passed") is True
        and isinstance(quiescence, dict)
        and quiescence.get("passed") is True
        and document.get("complete_removal") is True
        and document.get("live_owner_service_preserved") is True
        and document.get("managed_service_inactive") is True
    )


def write(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)
