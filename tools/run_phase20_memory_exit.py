#!/usr/bin/env python3
"""Build and qualify signed installed Phase 20.1 ephemeral session memory."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.phase19_exit.release_environment import build_and_install
from tools.phase20_memory_exit.installed_service import InstalledMemoryService
from tools.phase20_memory_exit.scenario import first_process_scenario, restarted_process_scenario


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/memory/phase20.1-session-memory.json"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        installation, manifest, _connector, _extensions = build_and_install(
            repository, root, "phase20-memory-exit", "phase20-memory-test",
        )
        product_root = root / "product"
        product_root.mkdir()
        with InstalledMemoryService(
            installation, repository, product_root, root / "run-1",
            ("Acknowledged ORBIT.", "ORBIT.", "UNKNOWN"),
        ) as service:
            first = first_process_scenario(service)
        first_observations = _read(service.observations)
        with InstalledMemoryService(
            installation, repository, product_root, root / "run-2", ("UNKNOWN",),
        ) as restarted:
            second = restarted_process_scenario(restarted)
        restart_observations = _read(restarted.observations)
        diagnosis = installation.diagnose()
        database = product_root / "state/state/fam.sqlite3"
        document = {
            "phase": "20.1",
            "release_id": manifest.release_id,
            "signer_key_id": manifest.signer_key_id,
            "release_component_count": len(manifest.components),
            "signed_install_healthy": diagnosis.healthy,
            "first_process": first,
            "first_process_observations": first_observations,
            "restarted_process": second,
            "restart_observations": restart_observations,
            "durable_database_contains_plaintext_nonce": (
                database.is_file() and b"ORBIT" in database.read_bytes()
            ),
        }
        document["passed"] = _passed(document)
        installation.remove()
        document["complete_removal"] = not installation.prefix.exists()
        document["passed"] = document["passed"] and document["complete_removal"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["passed"] else 1


def _read(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _passed(document: dict) -> bool:
    first = document["first_process_observations"]
    restarted = document["restart_observations"]
    return bool(
        document["signed_install_healthy"]
        and document["release_component_count"] == 7
        and len(first) == 3 and len(restarted) == 1
        and not first[0]["contains_memory_header"]
        and first[1]["contains_memory_header"]
        and first[1]["contains_prior_user_turn"]
        and first[1]["contains_prior_assistant_turn"]
        and first[1]["contains_authority_warning"]
        and not first[2]["contains_memory_header"]
        and not restarted[0]["contains_memory_header"]
        and not document["durable_database_contains_plaintext_nonce"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
