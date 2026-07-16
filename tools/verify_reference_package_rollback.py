#!/usr/bin/env python3
"""Exercise retained strong-package rollback and restore against installed models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fam_os.adapters.filesystem import JsonPackageLifecycleStateStore
from fam_os.adapters.ollama import (
    OllamaModelArtifactStore,
    OllamaModelCatalog,
    OllamaSettings,
)
from fam_os.registry.lifecycle import ExpertPackageLifecycle


STRONG_EXPERT_IDS = (
    "expert.code.gemma4-26b",
    "expert.code.laguna-xs2-33b",
)


def verify(args) -> dict[str, object]:
    state_store = JsonPackageLifecycleStateStore(args.state)
    lifecycle = ExpertPackageLifecycle(
        state_store,
        OllamaModelArtifactStore(
            OllamaModelCatalog(OllamaSettings(args.ollama_url, args.timeout_seconds))
        ),
    )
    evidence = []
    for expert_id in STRONG_EXPERT_IDS:
        versions = tuple(
            sorted(
                (item for item in state_store.load().packages if item.expert_id == expert_id),
                key=lambda item: item.coordinate.package_version,
            )
        )
        if len(versions) < 2:
            raise ValueError("rollback proof requires two installed strong-package versions")
        old, current = versions[-2], versions[-1]
        rolled_back = lifecycle.rollback(old.coordinate)
        restored = lifecycle.rollback(current.coordinate)
        evidence.append({
            "expert_id": expert_id,
            "rollback_coordinate": {
                "package_id": old.coordinate.package_id,
                "package_version": old.coordinate.package_version,
            },
            "restore_coordinate": {
                "package_id": current.coordinate.package_id,
                "package_version": current.coordinate.package_version,
            },
            "rollback_revision": rolled_back.revision,
            "restore_revision": restored.revision,
            "artifact_reverified": True,
        })
    state = state_store.load()
    return {
        "schema_version": 1,
        "state_revision": state.revision,
        "strong_package_rollbacks": evidence,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args()
    report = verify(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
