#!/usr/bin/env python3
"""Build and qualify signed installed Phase 21.3 minimum-context transfer."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.phase21_context_exit.scenario import run_context_scenario
from tools.phase21_peer_exit.release_environment import build_and_install_pair
from tools.phase21_peer_exit.scenario import run_installed_peer_scenario


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/fabric/phase21.3-minimum-context.json"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        pair = build_and_install_pair(repository, root)
        paired = run_installed_peer_scenario(pair, repository, root)
        scenario = run_context_scenario(pair, root, paired)
        document = {
            "phase": "21.3", "release_id": pair.manifest.release_id,
            "signer_key_id": pair.manifest.signer_key_id,
            "release_component_count": len(pair.manifest.components),
            "desktop_install_healthy": pair.desktop.diagnose().healthy,
            "server_install_healthy": pair.server.diagnose().healthy,
            "pairing_codes_match": paired["pairing_codes_match"],
            "scenario": scenario,
        }
        document["passed"] = _passed(document)
        pair.desktop.remove()
        pair.server.remove()
        document["complete_removal"] = (
            not pair.desktop.prefix.exists() and not pair.server.prefix.exists()
        )
        document["passed"] = document["passed"] and document["complete_removal"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["passed"] else 1


def _passed(document) -> bool:
    scenario = document["scenario"]
    shell = scenario["installed_shell"]
    return all((
        document["desktop_install_healthy"], document["server_install_healthy"],
        document["release_component_count"] == 7,
        document["pairing_codes_match"], scenario["privacy_revision_one"] == 1,
        scenario["descriptor_content_bytes"] > 0,
        scenario["descriptor_receipt_verified"],
        shell["returncode"] == 0,
        "context.receipt_verified" in shell["stdout"],
        all(scenario["denials"].values()),
        scenario["server_context_count_before_denials"]
        == scenario["server_context_count_after_denials"],
        scenario["privacy_revision_two"] == 2,
        scenario["raw_fragment_hash_count"] == 1,
        scenario["desktop_evidence_count"] == 3,
        scenario["server_evidence_count"] == 3,
        scenario["database_counts"] == {"desktop": 3, "server": 3},
        not scenario["evidence_contains_raw_content"],
        not scenario["database_contains_context_content"],
    ))


if __name__ == "__main__":
    raise SystemExit(main())
