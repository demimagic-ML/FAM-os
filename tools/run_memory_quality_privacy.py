#!/usr/bin/env python3
"""Run live encrypted retrieval quality and privacy checks."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.memory import MemoryAccessContext, MemoryScope
from fam_os.memory.document_contracts import DocumentIndexApproval
from fam_os.memory.document_index import ApprovedDocumentIndex
from fam_os.memory.document_repository import SqliteDocumentIndexRepository
from fam_os.memory.encryption import AesGcmMemoryCipher, OwnerMemoryKey
from fam_os.memory.quality_evidence import MemoryQualityCase, MemoryQualityPrivacyReport

DOCUMENTS = (
    ("hardware", "FAM coordinates the local GPU, CPU, RAM, and SSD."),
    ("permissions", "Memory retrieval requires matching owner, purpose, and workspace scope."),
    ("connectors", "Application connectors expose typed observations and reversible actions."),
)
QUERIES = (
    ("q-hardware", "Which local hardware resources does FAM coordinate?", "hardware"),
    ("q-permissions", "What controls whether memory can be retrieved?", "permissions"),
    ("q-connectors", "How do applications expose observations and actions?", "connectors"),
)


def main():
    root = Path(__file__).parents[1] / "artifacts/memory/phase10.7"
    root.mkdir(parents=True, exist_ok=True)
    database = root / "quality-privacy.sqlite"
    database.unlink(missing_ok=True)
    cipher = AesGcmMemoryCipher((OwnerMemoryKey("owner", "key-owner", b"k" * 32),))
    repository = SqliteDocumentIndexRepository(database, cipher)
    index = ApprovedDocumentIndex(repository, OllamaRuntime(OllamaSettings("http://127.0.0.1:11434", 180)))
    now = datetime.now(UTC)
    for document_id, content in DOCUMENTS:
        index.index(_approval(document_id, content, now), content, (content,))
    context = MemoryAccessContext("owner", "assist", workspace_id="FAM_OS")
    cases = tuple(_case(query_id, query, expected, index, context) for query_id, query, expected in QUERIES)
    denied = index.retrieve("hardware", MemoryAccessContext("other", "assist"), 10)
    repository.close()
    raw = database.read_bytes()
    leaks = sum(content.encode() in raw for _, content in DOCUMENTS)
    accuracy = sum(case.passed for case in cases) / len(cases)
    report = MemoryQualityPrivacyReport(
        "phase10.7-workstation-v1", cases, accuracy, len(denied), leaks,
        accuracy >= .8 and not denied and leaks == 0,
    )
    (root / "memory-quality-privacy.json").write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
    )


def _approval(document_id, content, now):
    return DocumentIndexApproval(
        document_id, f"fixture://{document_id}", hashlib.sha256(content.encode()).hexdigest(),
        MemoryScope("owner", ("assist",), workspace_ids=("FAM_OS",)), "owner", now,
        "nomic-embed-text:latest",
        "0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f",
    )


def _case(query_id, query, expected, index, context):
    observed = index.retrieve(query, context, 1)[0].document_id
    return MemoryQualityCase(query_id, expected, observed, expected == observed)


if __name__ == "__main__":
    main()
