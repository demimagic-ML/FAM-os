#!/usr/bin/env python3
"""Run live inspect, correct, export, and delete evidence."""

import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.memory import MemoryAccessContext, MemoryScope
from fam_os.memory.document_contracts import DocumentIndexApproval
from fam_os.memory.document_index import ApprovedDocumentIndex
from fam_os.memory.document_repository import SqliteDocumentIndexRepository
from fam_os.memory.lifecycle_contracts import MemoryDeletionReason, MemoryDeletionRequest
from fam_os.memory.management import DocumentMemoryManager, MemoryManagementEvidence


def main():
    root = Path(__file__).parents[1] / "artifacts/memory/phase10.5"
    root.mkdir(parents=True, exist_ok=True)
    database = root / "managed-memory.sqlite"
    database.unlink(missing_ok=True)
    now = datetime.now(UTC)
    original, corrected = "FAM uses local RAM.", "FAM uses local GPU, CPU, RAM, and SSD."
    approval = _approval(original, now)
    repository = SqliteDocumentIndexRepository(database)
    index = ApprovedDocumentIndex(repository, OllamaRuntime(OllamaSettings("http://127.0.0.1:11434", 180)))
    manager = DocumentMemoryManager(repository, index)
    context = MemoryAccessContext("user.local", "assist", workspace_id="FAM_OS")
    index.index(approval, original, (original,))
    inspected = manager.inspect("managed-doc", context) is not None
    manager.correct(replace(approval, source_sha256=_digest(corrected)), corrected, (corrected,), context)
    exported = manager.export("managed-doc", context)
    receipt = manager.delete(MemoryDeletionRequest(
        "delete-managed", "managed-doc", "user.local", "user.local", now,
        MemoryDeletionReason.USER_REQUEST,
    ), context, now)
    evidence = MemoryManagementEvidence(
        "phase10.5-workstation-v1", inspected, exported.content == corrected,
        exported.content_sha256 == _digest(corrected), receipt.payload_removed,
        len(repository.chunks("managed-doc")), True,
    )
    repository.close()
    (root / "memory-management-evidence.json").write_text(
        json.dumps(asdict(evidence), indent=2, sort_keys=True) + "\n",
    )


def _approval(content, now):
    return DocumentIndexApproval(
        "managed-doc", "fixture://managed", _digest(content),
        MemoryScope("user.local", ("assist",), workspace_ids=("FAM_OS",)),
        "user.local", now, "nomic-embed-text:latest",
        "0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f",
    )


def _digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


if __name__ == "__main__":
    main()
