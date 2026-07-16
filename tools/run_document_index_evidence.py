#!/usr/bin/env python3
"""Run live approved document indexing with Nomic embeddings."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from fam_os.adapters.ollama import OllamaModelCatalog, OllamaRuntime, OllamaSettings
from fam_os.memory.access import MemoryAccessContext
from fam_os.memory.document_contracts import DocumentIndexApproval, DocumentIndexEvidence
from fam_os.memory.document_index import ApprovedDocumentIndex
from fam_os.memory.document_repository import SqliteDocumentIndexRepository
from fam_os.memory.manifest import MemoryScope

ROOT = Path(__file__).parents[1]


def main():
    directory = ROOT / "artifacts/memory/phase10.3"
    directory.mkdir(parents=True, exist_ok=True)
    database = directory / "approved-documents.sqlite"
    database.unlink(missing_ok=True)
    content = "FAM coordinates GPU, CPU, RAM, and SSD.\nMemory retrieval obeys owner and workspace scope."
    chunks = ("FAM coordinates GPU, CPU, RAM, and SSD.\n",
              "Memory retrieval obeys owner and workspace scope.")
    settings = OllamaSettings("http://127.0.0.1:11434", 180)
    artifact = OllamaModelCatalog(settings).observe("nomic-embed-text:latest")
    approval = DocumentIndexApproval(
        "fam-overview", "fixture://fam-overview", _digest_text(content),
        MemoryScope("user.local", ("assist",), workspace_ids=("FAM_OS",)),
        "user.local", datetime.now(UTC), "nomic-embed-text:latest", artifact.digest.value,
    )
    repository = SqliteDocumentIndexRepository(database)
    index = ApprovedDocumentIndex(repository, OllamaRuntime(settings))
    index.index(approval, content, chunks)
    allowed = index.retrieve(
        "Which hardware resources does FAM coordinate?",
        MemoryAccessContext("user.local", "assist", workspace_id="FAM_OS"), 1,
    )
    denied = index.retrieve(
        "hardware", MemoryAccessContext("other-user", "assist"), 5,
    )
    repository.close()
    evidence = DocumentIndexEvidence(
        "phase10.3-workstation-v1", approval.document_id, approval.source_sha256,
        approval.embedding_model_ref, approval.embedding_artifact_sha256,
        len(chunks), allowed[0].chunk_id, len(denied), _digest_file(database),
        bool(allowed) and not denied,
    )
    (directory / "document-index-evidence.json").write_text(
        json.dumps(asdict(evidence), indent=2, sort_keys=True) + "\n",
    )


def _digest_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _digest_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
