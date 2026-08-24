#!/usr/bin/env python3
"""Build and qualify signed installed Phase 21.6 remote-loss recovery."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.phase21_peer_exit.release_environment import build_and_install_pair
from tools.phase21_peer_exit.scenario import run_installed_peer_scenario
from tools.phase21_recovery_exit.scenario import run_recovery_scenario
from tools.phase21_recovery_exit.validation import phase21_6_passed


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/fabric/phase21.6-remote-loss-recovery.json"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        pair = build_and_install_pair(repository, root)
        try:
            paired = run_installed_peer_scenario(pair, repository, root)
            scenario = run_recovery_scenario(pair, repository, root, paired)
            document = {
                "phase": "21.6",
                "release_id": pair.manifest.release_id,
                "signer_key_id": pair.manifest.signer_key_id,
                "release_component_count": len(pair.manifest.components),
                "desktop_install_healthy": pair.desktop.diagnose().healthy,
                "server_install_healthy": pair.server.diagnose().healthy,
                "pairing_codes_match": paired["pairing_codes_match"],
                "same_host_limitation": (
                    "Two isolated signed installations exercise process and peer loss "
                    "on one workstation; Phase 21.7 still requires two physical "
                    "Linux machines."
                ),
                "scenario": scenario,
            }
            document["passed"] = phase21_6_passed(document)
        finally:
            pair.desktop.remove()
            pair.server.remove()
        document["complete_removal"] = (
            not pair.desktop.prefix.exists() and not pair.server.prefix.exists()
        )
        document["passed"] = document["passed"] and document["complete_removal"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
