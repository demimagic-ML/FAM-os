#!/usr/bin/env python3
"""Build and qualify signed installed Phase 20.2 document indexing."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from tools.phase19_exit.release_environment import build_and_install
from tools.phase20_index_exit.installed_service import InstalledIndexService
from tools.phase20_index_exit.model_root import create_model_root
from tools.phase20_index_exit.scenario import first_process_scenario, restarted_process_scenario


NONCE = b"PHASE20_INDEX_PRIVATE_NONCE"


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/memory/phase20.2-document-indexing.json"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        installation, manifest, _connector, _extensions = build_and_install(
            repository, root, "phase20-index-exit", "phase20-index-test",
        )
        model_root = create_model_root(root / "models")
        long_root, short_file = _documents(root / "documents")
        product_root = root / "product"
        product_root.mkdir()
        with InstalledIndexService(
            installation, repository, product_root, model_root, root / "run-1",
        ) as service:
            first = first_process_scenario(service, long_root, short_file)
        database = product_root / "state/state/fam.sqlite3"
        database_counts = _counts(database)
        plaintext_found = any(
            NONCE in path.read_bytes()
            for path in database.parent.glob("fam.sqlite3*") if path.is_file()
        )
        with InstalledIndexService(
            installation, repository, product_root, model_root, root / "run-2",
        ) as restarted:
            second = restarted_process_scenario(restarted)
        diagnosis = installation.diagnose()
        document = {
            "phase": "20.2",
            "release_id": manifest.release_id,
            "signer_key_id": manifest.signer_key_id,
            "release_component_count": len(manifest.components),
            "signed_install_healthy": diagnosis.healthy,
            "first_process": first,
            "database_counts_after_expiry": database_counts,
            "durable_database_contains_plaintext_nonce": plaintext_found,
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


def _documents(root: Path) -> tuple[Path, Path]:
    long_root = root / "long"
    long_root.mkdir(parents=True)
    (long_root / "README.md").write_bytes(NONCE + b" project identity")
    nested = long_root / "nested"
    nested.mkdir()
    (nested / "notes.txt").write_text("bounded nested note", encoding="utf-8")
    (long_root / "ignored.bin").write_bytes(NONCE + b" ignored")
    (long_root / "linked.txt").symlink_to(nested / "notes.txt")
    short_file = root / "short.txt"
    short_file.write_text("short lived document", encoding="utf-8")
    return long_root, short_file


def _counts(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(path)
    try:
        return {
            name: connection.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            for name in (
                "document_index_grants", "document_index_documents",
                "document_index_chunks",
            )
        }
    finally:
        connection.close()


def _passed(document: dict) -> bool:
    first = document["first_process"]
    long_receipt = first["long_receipt"]
    short_receipt = first["short_receipt"]
    after = first["after_expiry"]
    restarted = document["restarted_process"]["indexes"]
    counts = document["database_counts_after_expiry"]
    return bool(
        document["signed_install_healthy"]
        and document["release_component_count"] == 7
        and first["before"] == []
        and first["denied_without_confirmation"]
        and long_receipt["passed"] and len(long_receipt["indexed_document_ids"]) == 2
        and long_receipt["skipped_paths"] == ["linked.txt"]
        and short_receipt["passed"] and len(first["cross_session"]) == 2
        and len(after) == 1 and after[0]["grant_id"] == long_receipt["grant_id"]
        and counts == {
            "document_index_grants": 1,
            "document_index_documents": 2,
            "document_index_chunks": 2,
        }
        and len(restarted) == 1 and restarted[0]["grant_id"] == long_receipt["grant_id"]
        and not document["durable_database_contains_plaintext_nonce"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
