#!/usr/bin/env python3
"""Build and qualify the signed installed Phase 21.4 remote Core route."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.phase21_peer_exit.release_environment import build_and_install_pair
from tools.phase21_peer_exit.scenario import run_installed_peer_scenario
from tools.phase21_remote_exit.scenario import run_remote_scenario
from tools.phase21_remote_exit.validation import phase21_4_passed


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/fabric/phase21.4-remote-core-route.json"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        pair = build_and_install_pair(repository, root)
        paired = run_installed_peer_scenario(pair, repository, root)
        scenario = run_remote_scenario(pair, repository, root, paired)
        document = {
            "phase": "21.4",
            "release_id": pair.manifest.release_id,
            "signer_key_id": pair.manifest.signer_key_id,
            "release_component_count": len(pair.manifest.components),
            "desktop_install_healthy": pair.desktop.diagnose().healthy,
            "server_install_healthy": pair.server.diagnose().healthy,
            "pairing_codes_match": paired["pairing_codes_match"],
            "same_host_limitation": (
                "Two isolated signed installations communicate over mutual TLS on "
                "one physical workstation; Phase 21.7 still requires two machines."
            ),
            "scenario": scenario,
        }
        document["passed"] = phase21_4_passed(document)
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


if __name__ == "__main__":
    raise SystemExit(main())
