#!/usr/bin/env python3
"""Build and qualify signed installed Phase 18.6 production verifiers."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from tools.phase18_verifier_exit.installed_service import InstalledVerifierService
from tools.phase18_verifier_exit.scenario import media_response, run_scenario, scripted_responses
from tools.phase19_exit.release_environment import build_and_install


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/verification/phase18-production-verifiers.json"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        installation, manifest, _connector, _extensions = build_and_install(
            repository, root, "phase18-verifier-exit", "phase18-verifier-test",
        )
        service_root = root / "service"
        service_root.mkdir()
        image_bytes = b"\x89PNG\r\n\x1a\nFAM_OS"
        image_digest = hashlib.sha256(image_bytes).hexdigest()
        responses = (*scripted_responses()[:-1], media_response(image_digest))
        with InstalledVerifierService(
            installation, repository, service_root, responses,
        ) as service:
            scenario = run_scenario(
                service, manifest.release_id, manifest.signer_key_id,
            )
        observations = json.loads(service.observations.read_text(encoding="utf-8"))
        diagnosis = installation.diagnose()
        document = {
            "phase": "18.6",
            "release_id": manifest.release_id,
            "signer_key_id": manifest.signer_key_id,
            "release_component_count": len(manifest.components),
            "signed_install_healthy": diagnosis.healthy,
            "scenario": scenario,
            "runtime_observations": observations,
            "media_image_forwarded": observations[-1]["image_count"] == 1,
            "all_json_domains_requested_json": all(
                item["json_output"] for item in observations[2:]
            ),
        }
        document["passed"] = (
            document["signed_install_healthy"]
            and document["release_component_count"] == 7
            and len(scenario["tasks"]) == 5
            and document["media_image_forwarded"]
            and document["all_json_domains_requested_json"]
        )
        installation.remove()
        document["complete_removal"] = not installation.prefix.exists()
        document["passed"] = document["passed"] and document["complete_removal"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
