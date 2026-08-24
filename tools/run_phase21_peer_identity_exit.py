#!/usr/bin/env python3
"""Build and qualify signed installed Phase 21.1 peer identity and mTLS."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.phase21_peer_exit.release_environment import build_and_install_pair
from tools.phase21_peer_exit.scenario import run_installed_peer_scenario


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/fabric/phase21.1-persistent-mtls.json"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        pair = build_and_install_pair(repository, root)
        scenario = run_installed_peer_scenario(pair, repository, root)
        document = {
            "phase": "21.1",
            "release_id": pair.manifest.release_id,
            "signer_key_id": pair.manifest.signer_key_id,
            "release_component_count": len(pair.manifest.components),
            "desktop_install_healthy": pair.desktop.diagnose().healthy,
            "server_install_healthy": pair.server.diagnose().healthy,
            "scenario": {
                key: value for key, value in scenario.items()
                if key not in {"desktop_state", "server_state"}
            },
        }
        document["passed"] = _passed(document)
        pair.desktop.remove()
        pair.server.remove()
        document["complete_removal"] = bool(
            not pair.desktop.prefix.exists() and not pair.server.prefix.exists()
        )
        document["passed"] = document["passed"] and document["complete_removal"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["passed"] else 1


def _passed(document: dict) -> bool:
    scenario = document["scenario"]
    first = scenario["first_authenticated_health"]
    second = scenario["restarted_authenticated_health"]
    return all((
        document["desktop_install_healthy"], document["server_install_healthy"],
        document["release_component_count"] == 7,
        scenario["pairing_codes_match"], scenario["unconfirmed_approval_denied"],
        scenario["server_identity_stable"],
        not scenario["database_contains_peer_display_names"],
        scenario["credential_modes_private"],
        first["peer"]["tls_version"] == "TLSv1.3",
        second["peer"]["tls_version"] == "TLSv1.3",
        first["response"]["status"] == "ready",
        second["response"]["status"] == "ready",
    ))


if __name__ == "__main__":
    raise SystemExit(main())
