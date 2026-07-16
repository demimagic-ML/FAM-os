import hashlib
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from tests.unit.test_approved_document_index import Runtime
from fam_os.memory import MemoryAccessContext, MemoryScope
from fam_os.memory.document_contracts import DocumentIndexApproval
from fam_os.memory.document_index import ApprovedDocumentIndex
from fam_os.memory.document_repository import SqliteDocumentIndexRepository
from fam_os.memory.lifecycle_contracts import MemoryDeletionReason, MemoryDeletionRequest
from fam_os.memory.management import DocumentMemoryManager

NOW = datetime(2026, 7, 16, tzinfo=UTC)


def approval(content):
    return DocumentIndexApproval(
        "doc", "fixture://doc", hashlib.sha256(content.encode()).hexdigest(),
        MemoryScope("owner", ("assist",), workspace_ids=("workspace",)),
        "owner", NOW, "embed:model", "a" * 64,
    )


class DocumentMemoryManagementTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SqliteDocumentIndexRepository(Path(self.directory.name) / "memory.sqlite")
        self.index = ApprovedDocumentIndex(self.repository, Runtime())
        self.manager = DocumentMemoryManager(self.repository, self.index)
        self.context = MemoryAccessContext("owner", "assist", workspace_id="workspace")
        self.index.index(approval("GPU memory"), "GPU memory", ("GPU memory",))

    def tearDown(self):
        self.repository.close()
        self.directory.cleanup()

    def test_inspect_export_and_atomic_correction(self):
        self.assertEqual("doc", self.manager.inspect("doc", self.context).document_id)
        self.assertEqual("GPU memory", self.manager.export("doc", self.context).content)
        self.manager.correct(approval("GPU and CPU memory"), "GPU and CPU memory",
                             ("GPU and CPU memory",), self.context)
        self.assertEqual("GPU and CPU memory", self.manager.export("doc", self.context).content)

    def test_denied_user_cannot_inspect_or_delete(self):
        denied = MemoryAccessContext("other", "assist")
        self.assertIsNone(self.manager.inspect("doc", denied))
        request = MemoryDeletionRequest("delete", "doc", "owner", "owner", NOW,
                                        MemoryDeletionReason.USER_REQUEST)
        with self.assertRaises(PermissionError):
            self.manager.delete(request, denied, NOW)

    def test_delete_cascades_chunks_then_returns_receipt(self):
        request = MemoryDeletionRequest("delete", "doc", "owner", "owner", NOW,
                                        MemoryDeletionReason.USER_REQUEST)
        receipt = self.manager.delete(request, self.context, NOW)
        self.assertTrue(receipt.payload_removed)
        self.assertIsNone(self.repository.document("doc"))
        self.assertEqual([], self.repository.chunks("doc"))


if __name__ == "__main__":
    unittest.main()
