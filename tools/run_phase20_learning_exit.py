#!/usr/bin/env python3
"""Build and qualify signed installed Phase 20.5 verified-outcome learning."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.phase19_exit.release_environment import build_and_install
from tools.phase20_learning_exit.installed_service import InstalledLearningService
from tools.phase20_learning_exit.scenario import (
    REDACTION,
    UNVERIFIED_OUTPUT,
    UNVERIFIED_PROMPT,
    VERIFIED_OUTPUT,
    VERIFIED_PROMPT,
    inspect_state,
    run_client,
)


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/adaptation/phase20.5-verified-learning.json"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        installation, manifest, _connector, _extensions = build_and_install(
            repository, root, "phase20-learning-exit", "phase20-learning-test",
        )
        product_root = root / "product"
        product_root.mkdir()
        with InstalledLearningService(
            installation, repository, product_root, root / "run-1",
            (VERIFIED_OUTPUT, UNVERIFIED_OUTPUT),
        ) as service:
            first = run_client(installation, repository, service, "submit")
        first_state = inspect_state(
            installation, repository, product_root, root / "first-state.json",
        )
        plaintext = _plaintext_found(product_root / "state/state")
        with InstalledLearningService(
            installation, repository, product_root, root / "run-2", (),
        ) as restarted:
            second = run_client(installation, repository, restarted, "restart")
        second_state = inspect_state(
            installation, repository, product_root, root / "second-state.json",
        )
        diagnosis = installation.diagnose()
        document = {
            "phase": "20.5",
            "release_id": manifest.release_id,
            "signer_key_id": manifest.signer_key_id,
            "release_component_count": len(manifest.components),
            "signed_install_healthy": diagnosis.healthy,
            "first_process": first,
            "first_shutdown_state": first_state,
            "durable_database_contains_plaintext_nonce": plaintext,
            "restarted_process": second,
            "restart_shutdown_state": second_state,
        }
        document["passed"] = _passed(document)
        installation.remove()
        document["complete_removal"] = not installation.prefix.exists()
        document["passed"] = document["passed"] and document["complete_removal"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["passed"] else 1


def _plaintext_found(root: Path) -> bool:
    nonces = tuple(value.encode() for value in (
        VERIFIED_PROMPT, UNVERIFIED_PROMPT, VERIFIED_OUTPUT, UNVERIFIED_OUTPUT,
    ))
    return any(
        nonce in path.read_bytes()
        for path in root.glob("fam.sqlite3*") if path.is_file()
        for nonce in nonces
    )


def _passed(document: dict) -> bool:
    first = document["first_process"]["results"]
    restarted = document["restarted_process"]["results"]
    state = document["first_shutdown_state"]
    restart_state = document["restart_shutdown_state"]
    learning = state["learning_records"]
    serialized_learning = json.dumps(learning, sort_keys=True)
    return bool(
        document["signed_install_healthy"]
        and document["release_component_count"] == 7
        and first[0]["status"] == "verified"
        and first[0]["assurance"] == "verified"
        and first[0]["verified"]
        and first[0]["content"] == VERIFIED_OUTPUT
        and first[1]["status"] == "completed"
        and not first[1]["verified"]
        and first[1]["content"] == UNVERIFIED_OUTPUT
        and state["request_prompts"] == {
            "learning-unverified": REDACTION,
            "learning-verified": REDACTION,
        }
        and state["terminal_result_count"] == 2
        and state["learning_record_count"] == 1
        and state["verification_declaration_count"] == 0
        and len(state["candidate_contents"]) == 2
        and set(state["candidate_contents"].values()) == {REDACTION}
        and state["verification_run_feedback"] == [REDACTION]
        and len(learning) == 1
        and learning[0]["payload"]["verified"]
        and learning[0]["payload"]["local_only"]
        and not learning[0]["payload"]["prompt_retained"]
        and not learning[0]["payload"]["candidate_content_retained"]
        and not learning[0]["payload"]["source_content_retained"]
        and not learning[0]["payload"]["application_payload_retained"]
        and VERIFIED_PROMPT not in serialized_learning
        and UNVERIFIED_PROMPT not in serialized_learning
        and VERIFIED_OUTPUT not in serialized_learning
        and UNVERIFIED_OUTPUT not in serialized_learning
        and not document["durable_database_contains_plaintext_nonce"]
        and restarted == first
        and restart_state == state
    )


if __name__ == "__main__":
    raise SystemExit(main())
