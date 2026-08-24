#!/usr/bin/env python3
"""Build and qualify signed installed Phase 21.2 peer state and controls."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.phase21_peer_exit.release_environment import build_and_install_pair
from tools.phase21_peer_exit.scenario import run_installed_peer_scenario
from tools.phase21_state_exit.scenario import run_peer_state_scenario


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/fabric/phase21.2-peer-state-and-controls.json"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        pair = build_and_install_pair(repository, root)
        paired = run_installed_peer_scenario(pair, repository, root)
        scenario = run_peer_state_scenario(pair, repository, root, paired)
        document = {
            "phase": "21.2",
            "release_id": pair.manifest.release_id,
            "signer_key_id": pair.manifest.signer_key_id,
            "release_component_count": len(pair.manifest.components),
            "desktop_install_healthy": pair.desktop.diagnose().healthy,
            "server_install_healthy": pair.server.diagnose().healthy,
            "pairing": {
                key: value for key, value in paired.items()
                if key not in {"desktop_state", "server_state"}
            },
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
    counts = scenario["database_counts"]
    desktop_shell = scenario["desktop_installed_shell"]
    server_shell = scenario["server_installed_shell"]
    return all((
        document["desktop_install_healthy"], document["server_install_healthy"],
        document["release_component_count"] == 7,
        document["pairing"]["pairing_codes_match"],
        scenario["console_initial_peer_count"] == 1,
        bool(scenario["console_probed_models"]),
        scenario["console_measured_latency_ms"] >= 0,
        scenario["privacy_receipt"]["applied"],
        scenario["unconfirmed_revoke_denied"],
        scenario["before_revoke_health"]["returncode"] == 0,
        scenario["after_revoke_connection_denied"],
        scenario["revocation_receipt"]["applied"],
        scenario["post_revoke_discovery_count"] == 0,
        scenario["control_receipt_count"] == 2,
        scenario["live_listener_closed"], scenario["restart_listener_closed"],
        scenario["restart_discovery_count"] == 0,
        desktop_shell["returncode"] == 0 and "trusted=true" in desktop_shell["stdout"],
        "privacy | applied=true" in desktop_shell["stdout"],
        server_shell["returncode"] == 0 and "No records." in server_shell["stdout"],
        all(scenario["console_assets"].values()),
        counts["desktop"]["enrollments"] == 1,
        counts["desktop"]["capabilities"] >= 1,
        counts["desktop"]["performance"] >= 1,
        counts["desktop"]["privacy"] == 1,
        counts["server"]["enrollments"] == 1,
        counts["server"]["active_enrollments"] == 0,
        counts["server"]["capabilities"] >= 1,
        counts["server"]["performance"] >= 1,
        counts["server"]["privacy"] == 1,
        not scenario["database_contains_sensitive_labels"],
    ))


if __name__ == "__main__":
    raise SystemExit(main())
