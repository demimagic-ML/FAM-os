import hashlib
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.core.ports.embedding import EmbeddingResponse
from fam_os.memory import (
    ApprovedDocumentIndex,
    DocumentCorrectionRequest,
    DocumentDeletionRequest,
    DocumentExpirationRequest,
    DocumentIndexApproval,
    DocumentIndexGrant,
    DocumentIndexGrantKind,
    DocumentManagementOperation,
    MemoryScope,
)
from fam_os.product.document_management_service import ProductDocumentManagementService
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.product.storage.document_index_repository import SqliteProductDocumentIndexRepository


NOW = datetime(2026, 7, 17, 12, tzinfo=UTC)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _Runtime:
    def embed(self, request):
        vectors = tuple((1.0, float(index + 1)) for index, _ in enumerate(request.inputs))
        return EmbeddingResponse(request.model_ref, vectors, len(vectors), 0.01)


class _Loader:
    def __init__(self):
        self.models = []

    def ensure_model(self, model_ref):
        self.models.append(model_ref)


class ProductDocumentManagementServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        opened = SecureStorage(
            ProductionDatabase(StorageSettings(self.root / "fam.sqlite3", os.geteuid())),
            OwnerKeyStore(self.root / "master.key", os.geteuid()),
        ).open()
        if opened.database is None or opened.cipher is None:
            self.fail("secure storage did not open")
        self.database = opened.database
        self.cipher = opened.cipher
        self.owner = str(os.geteuid())
        self.repository = SqliteProductDocumentIndexRepository(
            self.database, self.cipher, self.owner,
        )
        self.index = ApprovedDocumentIndex(self.repository, _Runtime())
        self.loader = _Loader()
        self.service = ProductDocumentManagementService(
            self.repository, self.index, self.owner,
            self.loader, clock=lambda: NOW,
        )

    def tearDown(self) -> None:
        self.database.close()
        self.temporary.cleanup()

    def test_inspect_export_correct_replay_and_restart_receipt(self) -> None:
        grant = self._grant("grant-correct")
        self._index(grant, "doc-correct", "private original")
        inspected = self.service.inspect("doc-correct")
        self.assertEqual(_digest("private original"), inspected.content_sha256)
        self.assertEqual("private original", self.service.export("doc-correct").content)
        request = DocumentCorrectionRequest(
            "correct-1", "doc-correct", inspected.content_sha256,
            "private corrected", _digest("private corrected"), True,
        )

        receipt = self.service.correct(request)

        self.assertEqual(DocumentManagementOperation.CORRECT, receipt.operation)
        self.assertEqual("private corrected", self.service.export("doc-correct").content)
        self.assertEqual(receipt, self.service.correct(request))
        self.assertEqual(["embed:model"], self.loader.models)
        restarted = ProductDocumentManagementService(
            SqliteProductDocumentIndexRepository(self.database, self.cipher, self.owner),
            self.index, self.owner, clock=lambda: NOW,
        )
        self.assertEqual((receipt,), restarted.receipts())
        raw = (self.root / "fam.sqlite3").read_bytes()
        self.assertNotIn(b"private original", raw)
        self.assertNotIn(b"private corrected", raw)

    def test_stale_correction_and_reused_request_identity_fail_closed(self) -> None:
        grant = self._grant("grant-stale")
        self._index(grant, "doc-stale", "current")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.service.correct(DocumentCorrectionRequest(
                "correct-stale", "doc-stale", "a" * 64,
                "replacement", _digest("replacement"), True,
            ))
        first = self.service.delete(DocumentDeletionRequest(
            "request-reuse", "doc-stale", _digest("current"), True,
        ))
        self.assertTrue(first.payload_removed)
        with self.assertRaisesRegex(ValueError, "identity was reused"):
            self.service.expire(DocumentExpirationRequest(
                "request-reuse", grant.grant_id, True,
            ))

    def test_delete_and_grant_expiry_cascade_payloads_but_keep_receipts(self) -> None:
        deleted_grant = self._grant("grant-delete")
        self._index(deleted_grant, "doc-delete", "delete me")
        deletion = self.service.delete(DocumentDeletionRequest(
            "delete-1", "doc-delete", _digest("delete me"), True,
        ))
        self.assertIsNone(self.repository.approval("doc-delete"))

        expired_grant = self._grant("grant-expire")
        self._index(expired_grant, "doc-expire-a", "first")
        self._index(expired_grant, "doc-expire-b", "second")
        expiration = self.service.expire(DocumentExpirationRequest(
            "expire-1", expired_grant.grant_id, True,
        ))

        self.assertIsNone(self.repository.grant(expired_grant.grant_id))
        self.assertIsNone(self.repository.approval("doc-expire-a"))
        self.assertEqual(
            ("doc-expire-a", "doc-expire-b"), expiration.affected_document_ids,
        )
        receipts = {item.operation: item for item in self.service.receipts()}
        self.assertEqual(deletion, receipts[DocumentManagementOperation.DELETE])
        self.assertEqual(expiration, receipts[DocumentManagementOperation.EXPIRE])

    def test_empty_grant_can_still_be_expired_with_a_durable_receipt(self) -> None:
        grant = self._grant("grant-empty")
        receipt = self.service.expire(DocumentExpirationRequest(
            "expire-empty", grant.grant_id, True,
        ))
        self.assertEqual((), receipt.affected_document_ids)
        self.assertTrue(receipt.payload_removed)
        self.assertIsNone(self.repository.grant(grant.grant_id))
        self.assertEqual((receipt,), self.service.receipts())

    def _grant(self, grant_id: str) -> DocumentIndexGrant:
        grant = DocumentIndexGrant(
            grant_id, f"/private/{grant_id}", DocumentIndexGrantKind.FOLDER,
            MemoryScope(self.owner, ("assist",), application_ids=("fam.mcp",)),
            True, (".md",), 8, 1024, 4096, self.owner,
            NOW - timedelta(hours=1), NOW + timedelta(days=1),
            "embed:model", "a" * 64,
        )
        self.assertTrue(self.repository.add_grant(grant))
        return grant

    def _index(self, grant, document_id: str, content: str) -> None:
        approval = DocumentIndexApproval(
            document_id, f"file:///private/{document_id}.md", _digest(content),
            grant.scope, self.owner, NOW, grant.embedding_model_ref,
            grant.embedding_artifact_sha256, grant_id=grant.grant_id,
            expires_at=grant.expires_at,
        )
        self.index.index(approval, content, (content,))


if __name__ == "__main__":
    unittest.main()
