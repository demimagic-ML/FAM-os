import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.core.ports.embedding import EmbeddingResponse
from fam_os.memory import (
    ApprovedDocumentIndex,
    DocumentIndexGrant,
    DocumentIndexGrantKind,
    MemoryScope,
)
from fam_os.memory.document_ingestion import SecureDocumentIngestor
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.product.storage.document_index_repository import (
    SqliteProductDocumentIndexRepository,
)


NOW = datetime(2026, 7, 17, 12, tzinfo=UTC)


class Runtime:
    def embed(self, request):
        vectors = tuple((float(len(value)), 1.0) for value in request.inputs)
        return EmbeddingResponse(request.model_ref, vectors, len(vectors), 0.01)


class Loader:
    def __init__(self):
        self.models = []

    def ensure_model(self, model_ref):
        self.models.append(model_ref)


class SecureDocumentIngestorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        database = ProductionDatabase(StorageSettings(self.root / "state.sqlite3", os.geteuid()))
        storage = SecureStorage(
            database, OwnerKeyStore(self.root / "master.key", os.geteuid()),
        ).open()
        if storage.database is None or storage.cipher is None:
            self.fail("secure storage did not open")
        self.database = storage.database
        self.owner = str(os.geteuid())
        self.repository = SqliteProductDocumentIndexRepository(
            storage.database, storage.cipher, self.owner,
        )
        self.loader = Loader()
        self.ingestor = SecureDocumentIngestor(
            self.repository, ApprovedDocumentIndex(self.repository, Runtime()),
            os.geteuid(), self.loader, lambda: NOW,
        )

    def tearDown(self):
        self.database.close()
        self.temporary.cleanup()

    def test_explicit_folder_grant_indexes_only_safe_allowlisted_files(self):
        folder = self.root / "documents"
        folder.mkdir()
        (folder / "a.md").write_text("A private project note", encoding="utf-8")
        (folder / "b.txt").write_text("B" * 9_000, encoding="utf-8")
        (folder / "ignored.bin").write_bytes(b"not indexed")
        nested = folder / "nested"
        nested.mkdir()
        (nested / "c.md").write_text("nested note", encoding="utf-8")
        (folder / "outside.md").symlink_to(nested / "c.md")

        self.assertEqual((), self.repository.grants())
        receipt = self.ingestor.index(self._grant(folder), confirmed=True)

        self.assertTrue(receipt.passed)
        self.assertEqual(3, len(receipt.indexed_document_ids))
        self.assertGreaterEqual(receipt.indexed_chunk_count, 4)
        self.assertEqual(("outside.md",), receipt.skipped_paths)
        self.assertEqual(["nomic-embed-text:latest"], self.loader.models)
        self.assertEqual(3, len(self.repository.document_ids(receipt.grant_id)))

    def test_denied_expired_symlink_and_over_file_bound_grants_store_nothing(self):
        folder = self.root / "bounded"
        folder.mkdir()
        (folder / "a.md").write_text("a", encoding="utf-8")
        (folder / "b.md").write_text("b", encoding="utf-8")
        grant = self._grant(folder, max_files=1)
        with self.assertRaises(PermissionError):
            self.ingestor.index(grant, confirmed=False)
        with self.assertRaisesRegex(ValueError, "file bound"):
            self.ingestor.index(grant, confirmed=True)
        self.assertEqual((), self.repository.grants())

        link = self.root / "linked"
        link.symlink_to(folder, target_is_directory=True)
        with self.assertRaisesRegex(OSError, "symlink"):
            self.ingestor.index(self._grant(link, grant_id="linked"), confirmed=True)
        self.assertEqual((), self.repository.grants())

        expired = self._grant(
            folder, grant_id="expired", approved_at=NOW - timedelta(days=2),
            expires_at=NOW - timedelta(days=1),
        )
        with self.assertRaisesRegex(PermissionError, "not active"):
            self.ingestor.index(expired, confirmed=True)

    def test_nonrecursive_grant_does_not_expand_into_subfolders(self):
        folder = self.root / "flat"
        folder.mkdir()
        (folder / "top.md").write_text("top", encoding="utf-8")
        nested = folder / "nested"
        nested.mkdir()
        (nested / "hidden.md").write_text("hidden", encoding="utf-8")
        receipt = self.ingestor.index(
            self._grant(folder, recursive=False), confirmed=True,
        )
        self.assertEqual(1, len(receipt.indexed_document_ids))

    def _grant(self, root, **changes):
        values = {
            "grant_id": "grant-1",
            "root_path": str(root),
            "kind": DocumentIndexGrantKind.FOLDER,
            "scope": MemoryScope(self.owner, ("assist",), workspace_ids=("workspace",)),
            "recursive": True,
            "allowed_extensions": (".md", ".txt"),
            "max_files": 16,
            "max_file_bytes": 32_768,
            "max_total_bytes": 131_072,
            "approved_by": self.owner,
            "approved_at": NOW,
            "expires_at": NOW + timedelta(days=7),
            "embedding_model_ref": "nomic-embed-text:latest",
            "embedding_artifact_sha256": "a" * 64,
        }
        values.update(changes)
        return DocumentIndexGrant(**values)


if __name__ == "__main__":
    unittest.main()
