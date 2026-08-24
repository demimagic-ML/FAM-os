"""Content-free aggregate identity and strict Phase 23.3 predicates."""

from __future__ import annotations

import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path

from .contracts import REQUIRED_SCENARIOS


CONTRACT_VERSION = "fam.product.installed-scenario-matrix/v1alpha1"


def initial_document(run_id: str, candidate) -> dict[str, object]:
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
        "scenarios": {},
        "complete_removal": False,
        "live_owner_service_preserved": False,
        "passed": False,
    }


def finalize(document: dict[str, object]) -> None:
    scenarios = document.get("scenarios")
    required = {item.value for item in REQUIRED_SCENARIOS}
    document["passed"] = bool(
        isinstance(scenarios, dict)
        and set(scenarios) == required
        and all(
            isinstance(value, dict) and value.get("passed") is True
            for value in scenarios.values()
        )
        and document.get("complete_removal") is True
        and document.get("live_owner_service_preserved") is True
    )


def write(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)

