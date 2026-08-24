import hashlib
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.core.ports.embedding import EmbeddingResponse
from fam_os.memory import (
    ApprovedDocumentIndex,
    DocumentIndexApproval,
    DocumentIndexGrant,
    DocumentIndexGrantKind,
    MemoryAccessContext,
    MemoryScope,
)
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.product.storage.document_index_repository import (
    SqliteProductDocumentIndexRepository,
)


NOW = datetime(2026, 7, 17, tzinfo=UTC)
CONTENT = "PHASE20_PRIVATE_NONCE: GPU and CPU cooperate."


class Runtime:
    def embed(self, request):
        vectors = tuple((1.0, 0.0) for _ in request.inputs)
        return EmbeddingResponse(request.model_ref, vectors, len(vectors), 0.01)


class ProductDocumentIndexRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        database = ProductionDatabase(StorageSettings(self.root / "fam.sqlite3", os.geteuid()))
        result = SecureStorage(
            database, OwnerKeyStore(self.root / "master.key", os.geteuid()),
        ).open()
        if result.database is None or result.cipher is None:
            self.fail("secure storage did not open")
        self.database = result.database
        self.owner = str(os.geteuid())
        self.repository = SqliteProductDocumentIndexRepository(
            result.database, result.cipher, self.owner,
        )
        self.index = ApprovedDocumentIndex(self.repository, Runtime())

    def tearDown(self):
        self.database.close()
        self.temporary.cleanup()

    def test_grant_document_and_chunks_are_encrypted_and_restart_safe(self):
        grant = self._grant()
        self.assertTrue(self.repository.add_grant(grant))
        self.index.index(self._approval(grant), CONTENT, (CONTENT,))
        context = MemoryAccessContext(self.owner, "assist", workspace_id="workspace")
        self.assertEqual(CONTENT, self.index.retrieve("GPU", context, now=NOW)[0].content)

        self.database.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        raw = (self.root / "fam.sqlite3").read_bytes()
        self.assertNotIn(b"PHASE20_PRIVATE_NONCE", raw)
        self.assertNotIn(b"/private/project", raw)
        self.assertEqual(("doc-1",), self.repository.document_ids(grant.grant_id))

    def test_expiry_hides_then_purges_documents_by_cascade(self):
        grant = self._grant(expires_at=NOW + timedelta(hours=1))
        self.assertTrue(self.repository.add_grant(grant))
        self.index.index(self._approval(grant), CONTENT, (CONTENT,))
        context = MemoryAccessContext(self.owner, "assist", workspace_id="workspace")
        self.assertEqual((), self.index.retrieve("GPU", context, now=grant.expires_at))
        self.assertEqual((grant.grant_id,), self.repository.purge_expired(grant.expires_at))
        self.assertIsNone(self.repository.approval("doc-1"))
        self.assertEqual((), self.repository.chunks("doc-1"))

    def test_document_cannot_exceed_or_bypass_grant(self):
        grant = self._grant()
        self.assertTrue(self.repository.add_grant(grant))
        ungranted = self._approval(grant, grant_id="missing")
        with self.assertRaises(PermissionError):
            self.index.index(ungranted, CONTENT, (CONTENT,))
        changed_scope = MemoryScope(self.owner, ("other",))
        with self.assertRaises(PermissionError):
            self.index.index(self._approval(grant, scope=changed_scope), CONTENT, (CONTENT,))

    def _grant(self, **changes):
        values = {
            "grant_id": "grant-1",
            "root_path": "/private/project",
            "kind": DocumentIndexGrantKind.FOLDER,
            "scope": MemoryScope(self.owner, ("assist",), workspace_ids=("workspace",)),
            "recursive": True,
            "allowed_extensions": (".md", ".txt"),
            "max_files": 8,
            "max_file_bytes": 1_048_576,
            "max_total_bytes": 4_194_304,
            "approved_by": self.owner,
            "approved_at": NOW,
            "expires_at": NOW + timedelta(days=7),
            "embedding_model_ref": "nomic-embed-text:latest",
            "embedding_artifact_sha256": "a" * 64,
        }
        values.update(changes)
        return DocumentIndexGrant(**values)

    def _approval(self, grant, **changes):
        values = {
            "document_id": "doc-1",
            "source_locator": "file:///private/project/readme.md",
            "source_sha256": hashlib.sha256(CONTENT.encode()).hexdigest(),
            "scope": grant.scope,
            "approved_by": self.owner,
            "approved_at": NOW,
            "embedding_model_ref": grant.embedding_model_ref,
            "embedding_artifact_sha256": grant.embedding_artifact_sha256,
            "grant_id": grant.grant_id,
            "expires_at": grant.expires_at,
        }
        values.update(changes)
        return DocumentIndexApproval(**values)


if __name__ == "__main__":
    unittest.main()
