import hashlib
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fam_os.core.ports.embedding import EmbeddingResponse
from fam_os.memory.access import MemoryAccessContext
from fam_os.memory.document_contracts import DocumentIndexApproval
from fam_os.memory.document_index import ApprovedDocumentIndex
from fam_os.memory.document_repository import SqliteDocumentIndexRepository
from fam_os.memory.manifest import MemoryScope

NOW = datetime(2026, 7, 16, tzinfo=UTC)
CONTENT = "GPU and CPU share work.Rain falls from clouds."


class Runtime:
    def embed(self, request):
        vectors = tuple((1.0, 0.0) if "GPU" in value or "hardware" in value else (0.0, 1.0)
                        for value in request.inputs)
        return EmbeddingResponse(request.model_ref, vectors, 1, .01)


def approval(scope=None, digest=None):
    return DocumentIndexApproval(
        "doc-1", "fixture://doc", digest or hashlib.sha256(CONTENT.encode()).hexdigest(),
        scope or MemoryScope("owner", ("assist",), workspace_ids=("workspace",)),
        "owner", NOW, "embed:model", "a" * 64,
    )


class ApprovedDocumentIndexTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SqliteDocumentIndexRepository(Path(self.directory.name) / "index.sqlite")
        self.index = ApprovedDocumentIndex(self.repository, Runtime())

    def tearDown(self):
        self.repository.close()
        self.directory.cleanup()

    def test_approved_digest_bound_chunks_are_scoped_and_retrievable(self):
        self.index.index(approval(), CONTENT, ("GPU and CPU share work.", "Rain falls from clouds."))
        context = MemoryAccessContext("owner", "assist", workspace_id="workspace")
        hits = self.index.retrieve("hardware", context, 1)
        self.assertEqual("GPU and CPU share work.", hits[0].content)
        denied = self.index.retrieve("hardware", MemoryAccessContext("other", "assist"))
        self.assertEqual((), denied)

    def test_tampered_source_or_incomplete_chunks_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "source digest"):
            self.index.index(approval(digest="b" * 64), CONTENT, (CONTENT,))
        with self.assertRaisesRegex(ValueError, "reconstruct"):
            self.index.index(approval(), CONTENT, ("partial",))


if __name__ == "__main__":
    unittest.main()
