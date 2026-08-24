import hashlib
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.core.ports.embedding import EmbeddingResponse
from fam_os.core.production import ModelIntent
from fam_os.core.production.grounding_port import (
    GroundedRetrievalUnavailable,
    GroundingAccessContext,
)
from fam_os.memory import (
    ApprovedDocumentIndex,
    DocumentIndexApproval,
    DocumentIndexGrant,
    DocumentIndexGrantKind,
    MemoryScope,
)
from fam_os.product.grounded_retrieval import ProductGroundedRetrieval
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.product.storage.document_index_repository import SqliteProductDocumentIndexRepository


NOW = datetime(2026, 7, 17, tzinfo=UTC)
CONTENT = "FAM Fabric schedules CPU, GPU, RAM, and SSD resources together."


class _Runtime:
    def embed(self, request):
        vectors = tuple((1.0, 0.0) for _ in request.inputs)
        return EmbeddingResponse(request.model_ref, vectors, len(vectors), 0.01)


class _Loader:
    def __init__(self):
        self.models = []

    def ensure_model(self, model_ref):
        self.models.append(model_ref)


class ProductGroundedRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        opened = SecureStorage(
            ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid())),
            OwnerKeyStore(root / "master.key", os.geteuid()),
        ).open()
        if opened.database is None or opened.cipher is None:
            self.fail("secure storage did not open")
        self.database = opened.database
        self.owner = str(os.geteuid())
        self.repository = SqliteProductDocumentIndexRepository(
            opened.database, opened.cipher, self.owner,
        )
        self.index = ApprovedDocumentIndex(self.repository, _Runtime())
        self.loader = _Loader()
        self.retrieval = ProductGroundedRetrieval(
            self.index, self.repository, self.owner,
            model_loader=self.loader, clock=lambda: NOW,
        )

    def tearDown(self) -> None:
        self.database.close()
        self.temporary.cleanup()

    def test_packaged_identity_is_available_without_document_authority(self) -> None:
        declaration = self.retrieval.declaration_for(
            "request-1", "Explain what FAM_OS is", ModelIntent.GROUNDED_QUESTION,
            GroundingAccessContext("fam.shell", "session-1"),
        )
        source = declaration.specification.sources[0]
        self.assertEqual("fam-os-product-identity", source.source_id)
        self.assertIn("not a replacement Linux kernel", source.content)
        self.assertEqual(("famos",), declaration.specification.query.required_terms)
        self.assertEqual((), tuple(self.loader.models))

    def test_full_product_name_resolves_to_the_same_identity_obligation(self) -> None:
        declaration = self.retrieval.declaration_for(
            "request-full-name",
            "What is the For All Mankind Operating System?",
            ModelIntent.GROUNDED_QUESTION,
            GroundingAccessContext("fam.shell", "session-full-name"),
        )

        source = declaration.specification.sources[0]
        self.assertEqual("fam-os-product-identity", source.source_id)
        self.assertEqual(("famos",), declaration.specification.query.required_terms)
        self.assertEqual((), tuple(self.loader.models))

    def test_mentioning_fam_os_does_not_route_an_unrelated_question_to_identity(self) -> None:
        with self.assertRaisesRegex(
            GroundedRetrievalUnavailable, "covered every significant request term",
        ):
            self.retrieval.declaration_for(
                "request-unrelated",
                "Answer briefly: is local FAM_OS residency smoke ready?",
                ModelIntent.GROUNDED_QUESTION,
                GroundingAccessContext("fam.shell", "session-unrelated"),
            )
        self.assertEqual([], self.loader.models)

    def test_approved_application_scope_yields_bounded_exact_source(self) -> None:
        grant = self._grant()
        self.assertTrue(self.repository.add_grant(grant))
        self.index.index(self._approval(grant), CONTENT, (CONTENT,))

        declaration = self.retrieval.declaration_for(
            "request-2", "What does this project schedule?",
            ModelIntent.GROUNDED_QUESTION,
            GroundingAccessContext("fam.shell", "session-2"),
        )

        source = declaration.specification.sources[0]
        self.assertEqual(CONTENT, source.content)
        self.assertEqual("file:///private/project/README.md", source.locator)
        self.assertTrue(source.provenance_id.startswith("document-index-"))
        self.assertEqual(("schedul",), declaration.specification.query.required_terms)
        self.assertEqual(["nomic-embed-text:latest"], self.loader.models)

    def test_cross_application_and_expired_grants_fail_closed(self) -> None:
        grant = self._grant()
        self.assertTrue(self.repository.add_grant(grant))
        self.index.index(self._approval(grant), CONTENT, (CONTENT,))
        denied = GroundingAccessContext("unapproved.application", "session-3")
        with self.assertRaises(GroundedRetrievalUnavailable):
            self.retrieval.declaration_for(
                "request-3", "search project resources", ModelIntent.RETRIEVAL, denied,
            )

        self.assertTrue(self.repository.delete_grant(grant.grant_id))
        expired = self._grant(
            grant_id="expired", approved_at=NOW - timedelta(days=2),
            expires_at=NOW - timedelta(days=1),
        )
        self.assertTrue(self.repository.add_grant(expired))
        with self.assertRaises(GroundedRetrievalUnavailable):
            self.retrieval.declaration_for(
                "request-4", "search expired notes", ModelIntent.RETRIEVAL,
                GroundingAccessContext("fam.shell", "session-4"),
            )
        self.assertNotIn("expired", {item.grant_id for item in self.repository.grants()})

    def _grant(self, **changes):
        values = {
            "grant_id": "grant-1",
            "root_path": "/private/project",
            "kind": DocumentIndexGrantKind.FOLDER,
            "scope": MemoryScope(self.owner, ("assist",), application_ids=("fam.shell",)),
            "recursive": True,
            "allowed_extensions": (".md",),
            "max_files": 8,
            "max_file_bytes": 1_048_576,
            "max_total_bytes": 4_194_304,
            "approved_by": self.owner,
            "approved_at": NOW - timedelta(hours=1),
            "expires_at": NOW + timedelta(days=7),
            "embedding_model_ref": "nomic-embed-text:latest",
            "embedding_artifact_sha256": "a" * 64,
        }
        values.update(changes)
        return DocumentIndexGrant(**values)

    def _approval(self, grant):
        return DocumentIndexApproval(
            "doc-1", "file:///private/project/README.md",
            hashlib.sha256(CONTENT.encode("utf-8")).hexdigest(), grant.scope,
            self.owner, grant.approved_at, grant.embedding_model_ref,
            grant.embedding_artifact_sha256, grant_id=grant.grant_id,
            expires_at=grant.expires_at,
        )


if __name__ == "__main__":
    unittest.main()
