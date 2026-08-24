import hashlib
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.crypto.documentation_recipes import (
    sign_documentation_recipe_specification,
)
from fam_os.adapters.crypto.engineering_recipes import Ed25519RecipeSignatureVerifier
from fam_os.adapters.sqlite import SQLiteEngineeringDocumentationStore
from fam_os.core.engineering import (
    DocumentationArtifactKind, DocumentationGenerationRequest,
    DocumentationGovernanceBinding,
    DocumentationRequirementSelection,
    DocumentationSource, DocumentationStalenessReport,
    GeneratedDocumentationReceipt, RequirementTraceabilityRecord,
    RequirementTraceStatus,
    SignedDocumentationRecipeCatalog,
)
from fam_os.core.engineering.production_documentation_recipes import (
    DocumentationRecipeSpecification,
)
from fam_os.product.engineering_documentation_api import (
    ProductEngineeringDocumentationApi,
)
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.keys import OwnerMasterKey
from fam_os.product.storage.owner_contract_codec import OwnerBoundContractCodec


NOW = datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc)
_DOCUMENT_TYPES = (
    DocumentationGenerationRequest, DocumentationGovernanceBinding,
    DocumentationRequirementSelection,
    GeneratedDocumentationReceipt,
    DocumentationStalenessReport, RequirementTraceabilityRecord,
)


class ProductEngineeringDocumentationApiTests(unittest.TestCase):
    def test_requirement_selection_is_policy_and_intent_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "candidate"
            _candidate_files(root)
            api = _api(
                root, SQLiteEngineeringDocumentationStore(
                    Path(temporary) / "documentation.sqlite3",
                ),
            )
            intent = "Update API docs"
            selection = DocumentationRequirementSelection(
                "selection-1", "task-1", "candidate-1",
                "fam.documentation.requirements.v1",
                hashlib.sha256(intent.encode()).hexdigest(),
                (DocumentationArtifactKind.API_REFERENCE,), NOW,
            )

            self.assertEqual(
                selection, api.record_selection("owner-1", selection),
            )
            with self.assertRaises(PermissionError):
                api.record_selection(
                    "owner-1", replace(selection, selection_id="selection-bad",
                                       intent_sha256="f" * 64),
                )
            with self.assertRaises(PermissionError):
                api.record_selection(
                    "owner-1", replace(
                        selection, selection_id="selection-missing", required_kinds=(),
                    ),
                )
            api.close()

    def test_signed_intent_survives_restart_and_unknown_recipe_has_no_effect(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "candidate"
            _candidate_files(root)
            request, receipt = _documents(root)
            store = SQLiteEngineeringDocumentationStore(
                base / "documentation.sqlite3",
            )
            api = _api(root, store)
            with self.assertRaises(LookupError):
                api.begin_generation(
                    "owner-1",
                    replace(request, generator_recipe_id="untrusted@1.0.0"),
                )
            self.assertEqual((), api.for_task("owner-1", "task-1"))
            api.begin_generation("owner-1", request)
            self.assertEqual((request,), api.for_task("owner-1", "task-1"))
            api.close()

            resumed = _api(
                root, SQLiteEngineeringDocumentationStore(
                    base / "documentation.sqlite3",
                ),
            )
            self.assertEqual(
                receipt, resumed.record_generated("owner-1", request, receipt),
            )
            resumed.close()

    def test_trusted_receipt_is_rehashed_and_staleness_blocks_passage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "candidate"
            _candidate_files(root)
            request, receipt = _documents(root)
            store = SQLiteEngineeringDocumentationStore(
                Path(temporary) / "documentation.sqlite3", _owner_codec(),
            )
            api = _api(root, store)
            api.begin_generation("owner-1", request)
            self.assertEqual(
                receipt, api.record_generated("owner-1", request, receipt),
            )
            self.assertTrue(any(
                isinstance(item, DocumentationGovernanceBinding)
                for item in api.for_task("owner-1", "task-1")
            ))
            reports = api.require_current("owner-1", "task-1")
            self.assertEqual(1, len(reports))
            self.assertFalse(reports[0].stale)
            self.assertEqual(
                reports, api.require_current("owner-1", "task-1"),
            )

            (root / "src/api.py").write_text("VALUE = 2\n")
            with self.assertRaisesRegex(PermissionError, "documentation is stale"):
                api.require_current("owner-1", "task-1")
            records = api.for_task("owner-1", "task-1")
            self.assertTrue(any(
                isinstance(item, DocumentationStalenessReport) and item.stale
                for item in records
            ))
            api.close()
            connection = sqlite3.connect(Path(temporary) / "documentation.sqlite3")
            documents = tuple(row[0] for row in connection.execute(
                "SELECT document FROM engineering_documentation"
            ).fetchall())
            connection.close()
            self.assertTrue(documents)
            self.assertTrue(all(
                item.startswith("fam.storage.aes256gcm/v1:") for item in documents
            ))
            self.assertFalse(any("VALUE = 1" in item for item in documents))

    def test_governance_file_digest_drift_blocks_passage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "candidate"
            _candidate_files(root)
            request, receipt = _documents(root)
            api = _api(
                root, SQLiteEngineeringDocumentationStore(
                    Path(temporary) / "documentation.sqlite3",
                ),
            )
            api.begin_generation("owner-1", request)
            api.record_generated("owner-1", request, receipt)
            (root / "docs/generated/FAM_REQUIREMENTS.md").write_text(
                "owner-modified requirement\n"
            )

            with self.assertRaisesRegex(PermissionError, "documentation is stale"):
                api.require_current("owner-1", "task-1")
            api.close()

    def test_satisfied_trace_requires_real_candidate_paths_and_trusted_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "candidate"
            _candidate_files(root)
            request, receipt = _documents(root)
            store = SQLiteEngineeringDocumentationStore(
                Path(temporary) / "documentation.sqlite3",
            )
            api = _api(root, store)
            api.begin_generation("owner-1", request)
            api.record_generated("owner-1", request, receipt)
            trace = RequirementTraceabilityRecord(
                "trace-1", "task-1", "requirement-1", "MASTER_PLANv2.md",
                ("src/api.py",), ("tests/test_api.py",),
                (receipt.receipt_id,), RequirementTraceStatus.SATISFIED, NOW,
            )
            self.assertEqual(trace, api.record_trace("owner-1", trace))
            missing = RequirementTraceabilityRecord(
                "trace-2", "task-1", "requirement-2", "MASTER_PLANv2.md",
                ("src/api.py",), ("tests/test_api.py",),
                ("claimed-receipt",), RequirementTraceStatus.SATISFIED, NOW,
            )
            with self.assertRaises(PermissionError):
                api.record_trace("owner-1", missing)
            api.close()

    def test_generated_output_symlink_is_rejected_even_when_digest_matches(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "candidate"
            _candidate_files(root)
            outside = base / "outside.md"
            outside.write_text("# API\n")
            (root / "docs/api.md").unlink()
            (root / "docs/api.md").symlink_to(outside)
            request, receipt = _documents(root)
            api = _api(
                root, SQLiteEngineeringDocumentationStore(
                    base / "documentation.sqlite3",
                ),
            )
            api.begin_generation("owner-1", request)
            with self.assertRaises(PermissionError):
                api.record_generated("owner-1", request, receipt)
            api.close()


def _candidate_files(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "tests").mkdir()
    (root / "src/api.py").write_text("VALUE = 1\n")
    (root / "docs/api.md").write_text("# API\n")
    (root / "docs/REGENERATE.md").write_text("Run signed recipe.\n")
    (root / "docs/generated").mkdir()
    (root / "docs/generated/FAM_REQUIREMENTS.md").write_text(
        "Task digest: fixture\n"
    )
    (root / "CODEOWNERS").write_text("docs/ @owner\n")
    (root / "MASTER_PLANv2.md").write_text("Requirement 1\n")
    (root / "tests/test_api.py").write_text("def test_api(): pass\n")


def _documents(root: Path):
    source = DocumentationSource(
        "src/api.py", hashlib.sha256((root / "src/api.py").read_bytes()).hexdigest(),
    )
    request = DocumentationGenerationRequest(
        "request-1", "task-1", "candidate-1",
        DocumentationArtifactKind.API_REFERENCE, "docs/api.md",
        "signed-generator-1@1.0.0", "CODEOWNERS", "docs/REGENERATE.md",
        (source,), NOW,
    )
    receipt = GeneratedDocumentationReceipt(
        "receipt-1", request.request_id, request.task_id, request.candidate_id,
        request.output_path,
        hashlib.sha256((root / "docs/api.md").read_bytes()).hexdigest(),
        request.generator_recipe_id, request.sources, NOW, True,
    )
    return request, receipt


def _api(root, store):
    candidate = SimpleNamespace(
        task_id="task-1", candidate_id="candidate-1",
        candidate_workspace=str(root),
    )
    return ProductEngineeringDocumentationApi(
        "owner-1", SimpleNamespace(
            load=lambda task_id: object(),
            load_task=lambda task_id: SimpleNamespace(
                task=SimpleNamespace(intent="Update API docs"),
            ),
        ),
        SimpleNamespace(load=lambda task_id: SimpleNamespace(candidate=candidate)),
        store, _recipe_catalog(),
    )


def _recipe_catalog():
    private = Ed25519PrivateKey.from_private_bytes(b"\x01" * 32)
    catalog = SignedDocumentationRecipeCatalog(
        Ed25519RecipeSignatureVerifier({"release-key": private.public_key()}),
    )
    catalog.admit(sign_documentation_recipe_specification(
        DocumentationRecipeSpecification(
            "signed-generator-1", DocumentationArtifactKind.API_REFERENCE,
            "fam.documentation.deterministic.v1", "text/markdown",
        ),
        "release-key", private,
    ))
    return catalog


def _owner_codec():
    key = bytes(range(32))
    key_id = "owner-key-" + hashlib.sha256(key).hexdigest()[:24]
    return OwnerBoundContractCodec(
        ProductPayloadCipher(OwnerMasterKey(key_id, key)), "owner-1",
        "engineering-documentation", _DOCUMENT_TYPES,
    )


if __name__ == "__main__":
    unittest.main()
