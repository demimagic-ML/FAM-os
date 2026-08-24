import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fam_os.core.ports.embedding import EmbeddingResponse
from fam_os.memory import ApprovedDocumentIndex
from fam_os.memory.document_ingestion import SecureDocumentIngestor
from fam_os.product.document_index_service import ProductDocumentIndexService
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.product.storage.document_index_repository import (
    SqliteProductDocumentIndexRepository,
)


NOW = datetime(2026, 7, 17, 12, tzinfo=UTC)


class Runtime:
    def embed(self, request):
        return EmbeddingResponse(
            request.model_ref, tuple((1.0, 0.0) for _ in request.inputs), 1, 0.01,
        )


class ProductDocumentIndexServiceTests(unittest.TestCase):
    def test_server_owns_identity_model_expiry_and_safe_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "project"
            source.mkdir()
            (source / "README.md").write_text("project identity", encoding="utf-8")
            database = ProductionDatabase(StorageSettings(root / "state.sqlite3", os.geteuid()))
            storage = SecureStorage(
                database, OwnerKeyStore(root / "master.key", os.geteuid()),
            ).open()
            if storage.database is None or storage.cipher is None:
                self.fail("secure storage did not open")
            owner = str(os.geteuid())
            repository = SqliteProductDocumentIndexRepository(
                storage.database, storage.cipher, owner,
            )
            ingestor = SecureDocumentIngestor(
                repository, ApprovedDocumentIndex(repository, Runtime()),
                os.geteuid(), clock=lambda: NOW,
            )
            service = ProductDocumentIndexService(
                repository, ingestor, owner, "nomic-embed-text:latest", "a" * 64,
                lambda: NOW,
            )
            receipt = service.create({
                "path": str(source), "kind": "folder", "recursive": True,
                "workspace_ids": ["workspace"], "allowed_extensions": [".md"],
                "expires_in_hours": 24, "confirmed": True,
            })
            self.assertTrue(receipt.passed)
            grant = repository.grant(receipt.grant_id)
            self.assertEqual(owner, grant.scope.owner_id)
            self.assertEqual("nomic-embed-text:latest", grant.embedding_model_ref)
            self.assertEqual(24 * 3600, (grant.expires_at - grant.approved_at).total_seconds())
            self.assertEqual(receipt.grant_id, service.list()[0]["grant_id"])
            storage.database.close()

    def test_unknown_fields_unsafe_extensions_and_missing_confirmation_fail_closed(self):
        class Unused:
            def purge_expired(self, _now): return ()
            def grants(self): return ()

        service = ProductDocumentIndexService(
            Unused(), None, str(os.geteuid()), "embed:model", "a" * 64,
            lambda: NOW,
        )
        baseline = {"path": "/tmp/project", "kind": "folder", "confirmed": True}
        for changes in (
            {"owner_id": "attacker"},
            {"allowed_extensions": [".sqlite"]},
            {"confirmed": False},
        ):
            with self.subTest(changes=changes), self.assertRaises((ValueError, PermissionError)):
                service.create(baseline | changes)


if __name__ == "__main__":
    unittest.main()
