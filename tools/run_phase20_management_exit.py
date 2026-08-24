#!/usr/bin/env python3
"""Build and qualify signed installed Phase 20.4 memory controls."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from tools.phase19_exit.release_environment import build_and_install
from tools.phase20_index_exit.installed_service import InstalledIndexService
from tools.phase20_index_exit.model_root import create_model_root
from tools.phase20_management_exit.scenario import (
    CONSOLE_CORRECTED_NONCE,
    DELETE_NONCE,
    EXPIRY_NONCE,
    ORIGINAL_NONCE,
    SHELL_CORRECTED_NONCE,
    first_process_scenario,
    restarted_process_scenario,
)


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/memory/phase20.4-memory-management.json"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        installation, manifest, _connector, _extensions = build_and_install(
            repository, root, "phase20-management-exit", "phase20-management-test",
        )
        model_root = create_model_root(root / "models")
        primary, folder, replacement = _documents(root / "documents")
        product_root = root / "product"
        product_root.mkdir()
        with InstalledIndexService(
            installation, repository, product_root, model_root, root / "run-1",
        ) as service:
            first = first_process_scenario(
                installation, service, primary, folder, replacement,
            )
        database = product_root / "state/state/fam.sqlite3"
        counts = _counts(database)
        plaintext = _plaintext_found(database.parent)
        with InstalledIndexService(
            installation, repository, product_root, model_root, root / "run-2",
        ) as restarted:
            second = restarted_process_scenario(installation, restarted, first)
        diagnosis = installation.diagnose()
        document = {
            "phase": "20.4",
            "release_id": manifest.release_id,
            "signer_key_id": manifest.signer_key_id,
            "release_component_count": len(manifest.components),
            "signed_install_healthy": diagnosis.healthy,
            "first_process": first,
            "database_counts_after_first_process": counts,
            "durable_database_contains_plaintext_nonce": plaintext,
            "restarted_process": second,
        }
        document["passed"] = _passed(document)
        installation.remove()
        document["complete_removal"] = not installation.prefix.exists()
        document["passed"] = document["passed"] and document["complete_removal"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["passed"] else 1


def _documents(root: Path) -> tuple[Path, Path, Path]:
    root.mkdir()
    primary = root / "primary.md"
    primary.write_text(ORIGINAL_NONCE, encoding="utf-8")
    folder = root / "managed-folder"
    folder.mkdir()
    (folder / "delete.txt").write_text(DELETE_NONCE, encoding="utf-8")
    (folder / "expire.txt").write_text(EXPIRY_NONCE, encoding="utf-8")
    replacement = root / "replacement.txt"
    replacement.write_text(SHELL_CORRECTED_NONCE, encoding="utf-8")
    return primary, folder, replacement


def _counts(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(path)
    try:
        return {
            table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in (
                "document_index_grants", "document_index_documents",
                "document_index_chunks", "document_management_receipts",
            )
        }
    finally:
        connection.close()


def _plaintext_found(root: Path) -> bool:
    nonces = tuple(value.encode() for value in (
        ORIGINAL_NONCE, SHELL_CORRECTED_NONCE, CONSOLE_CORRECTED_NONCE,
        DELETE_NONCE, EXPIRY_NONCE,
    ))
    return any(
        nonce in path.read_bytes()
        for path in root.glob("fam.sqlite3*") if path.is_file()
        for nonce in nonces
    )


def _passed(document: dict) -> bool:
    first = document["first_process"]
    second = document["restarted_process"]
    first_operations = [item["operation"] for item in first["receipts"]]
    second_operations = [item["operation"] for item in second["receipts_after"]]
    shell = first["installed_shell"]
    restart_shell = second["installed_shell"]
    return bool(
        document["signed_install_healthy"]
        and document["release_component_count"] == 7
        and first["before"] == []
        and first["primary_index"]["passed"]
        and first["folder_index"]["passed"]
        and first["initial_document_count"] == 3
        and first["explicit_confirmation_denied"]
        and shell["returncode"] == 0
        and ORIGINAL_NONCE in shell["stdout"]
        and "Command could not be completed safely." in shell["stdout"]
        and "Memory correct completed." in shell["stdout"]
        and first["shell_corrected_digest"] == _sha(SHELL_CORRECTED_NONCE)
        and first["console_correction"]["operation"] == "correct"
        and first["console_correction"]["resulting_content_sha256"] == _sha(
            CONSOLE_CORRECTED_NONCE
        )
        and first["console_deletion"]["operation"] == "delete"
        and first["console_deletion"]["payload_removed"]
        and first["console_expiration"]["operation"] == "expire"
        and first["console_expiration"]["payload_removed"]
        and first["expired_document_removed"]
        and first["remaining_document_ids"] == [first["primary_document_id"]]
        and first["final_export"]["content"] == CONSOLE_CORRECTED_NONCE
        and sorted(first_operations) == ["correct", "correct", "delete", "expire"]
        and first["installed_shell_export"]["returncode"] == 0
        and CONSOLE_CORRECTED_NONCE in first["installed_shell_export"]["stdout"]
        and all(first["console_assets"].values())
        and document["database_counts_after_first_process"] == {
            "document_index_grants": 1,
            "document_index_documents": 1,
            "document_index_chunks": 1,
            "document_management_receipts": 4,
        }
        and not document["durable_database_contains_plaintext_nonce"]
        and second["document_count_before"] == 1
        and second["exported_content"] == CONSOLE_CORRECTED_NONCE
        and len(second["receipts_before"]) == 4
        and restart_shell["returncode"] == 0
        and "Memory delete completed." in restart_shell["stdout"]
        and "Memory expire completed." in restart_shell["stdout"]
        and "Persistent memory: 0 shown of 0" in restart_shell["stdout"]
        and second["documents_after"] == []
        and second["indexes_after"] == []
        and sorted(second_operations) == [
            "correct", "correct", "delete", "delete", "expire", "expire",
        ]
        and second["delete_replay_same_receipt"]
    )


def _sha(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
