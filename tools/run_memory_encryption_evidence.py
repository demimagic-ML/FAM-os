#!/usr/bin/env python3
"""Build owner-isolated encrypted-memory evidence."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidTag

from fam_os.memory.document_index import ApprovedDocumentIndex
from fam_os.memory.document_repository import SqliteDocumentIndexRepository
from fam_os.memory.encryption import AesGcmMemoryCipher, MemoryEncryptionEvidence, OwnerMemoryKey
from fam_os.core.ports.embedding import EmbeddingResponse
from fam_os.memory.document_contracts import DocumentIndexApproval
from fam_os.memory.manifest import MemoryScope

CONTENT = "GPU and CPU share work.Rain falls from clouds."


class Runtime:
    def embed(self, request):
        return EmbeddingResponse(request.model_ref, tuple((1.0, 0.0) for _ in request.inputs), 1, .01)


def approval():
    return DocumentIndexApproval(
        "doc-1", "fixture://doc", hashlib.sha256(CONTENT.encode()).hexdigest(),
        MemoryScope("owner", ("assist",)), "owner", datetime.now(UTC),
        "embed:model", "a" * 64,
    )


def main():
    root = Path(__file__).parents[1] / "artifacts/memory/phase10.6"
    root.mkdir(parents=True, exist_ok=True)
    database = root / "encrypted-memory.sqlite"
    database.unlink(missing_ok=True)
    cipher = AesGcmMemoryCipher((OwnerMemoryKey("owner", "owner-key", b"k" * 32),
                                OwnerMemoryKey("other", "other-key", b"o" * 32)))
    repository = SqliteDocumentIndexRepository(database, cipher)
    ApprovedDocumentIndex(repository, Runtime()).index(
        approval(), CONTENT, ("GPU and CPU share work.", "Rain falls from clouds."),
    )
    owner_round_trip = repository.chunks("doc-1")[0][3] == "GPU and CPU share work."
    token = cipher.encrypt("owner", b"private")
    try:
        cipher.decrypt("other", token)
        rejected = False
    except (ValueError, InvalidTag):
        rejected = True
    repository.close()
    raw = database.read_bytes()
    plaintext_absent = b"GPU and CPU" not in raw and b"Rain falls" not in raw
    evidence = MemoryEncryptionEvidence(
        "phase10.6-workstation-v1", "AES-256-GCM", plaintext_absent,
        owner_round_trip, rejected, hashlib.sha256(raw).hexdigest(),
        plaintext_absent and owner_round_trip and rejected,
    )
    (root / "memory-encryption-evidence.json").write_text(
        json.dumps(asdict(evidence), indent=2, sort_keys=True) + "\n",
    )


if __name__ == "__main__":
    main()
