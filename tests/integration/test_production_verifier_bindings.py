import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from fam_os.console.tasks import ConsoleTaskApi
from fam_os.core.contracts import ResultStatus
from fam_os.core.production import ModelIntent, RuntimeModelEntry
from fam_os.core.production.gateway import ProductionTaskGateway
from fam_os.core.production.model_catalog import RuntimeModelCatalog
from fam_os.core.production.model_selection import HostCapacity, ResourceAwareModelSelector
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.composition.verifier_unit import _packages, production_verifier
from fam_os.schemas import loads_document
from fam_os.product.storage import (
    OwnerKeyStore,
    ProductionDatabase,
    SecureStorage,
    StorageSettings,
)
from fam_os.shell import ShellRunState


class ProductionVerifierBindingTests(unittest.TestCase):
    def test_production_package_composition_rejects_orphan_and_duplicate_bindings(
        self,
    ) -> None:
        binding_path = (
            Path("configs/packages/verifier-bindings")
            / "production-exact-text-v1.json"
        )
        binding = loads_document(binding_path.read_text(encoding="utf-8"))
        arguments = (None, None, "test-policy", None, None)

        with self.assertRaisesRegex(RuntimeError, "duplicate verifier IDs"):
            _packages((), (binding, binding), *arguments)
        with self.assertRaisesRegex(RuntimeError, "lack matching manifests"):
            _packages((), (binding,), *arguments)

    def test_every_declared_domain_runs_through_core_and_persists_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "ocr.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\nFAM_OS")
            image_digest = hashlib.sha256(image.read_bytes()).hexdigest()
            runtime = _Runtime((
                "READY",
                "def add(left, right):\n    return left + right\n",
                json.dumps({
                    "answer": "FAM_OS runs locally.",
                    "claims": [{
                        "text": "FAM_OS runs locally.", "source_id": "source-1",
                        "quote": "FAM_OS runs locally.",
                    }],
                }),
                json.dumps({"expression": "x**2 + 2*x + 1"}),
                json.dumps({
                    "artifact_sha256": image_digest, "observed_text": "FAM_OS",
                }),
            ))
            database, repositories, gateway = _gateway(root, runtime)
            api = ConsoleTaskApi(gateway)
            documents = (
                {
                    "request_id": "verify-exact", "prompt": "Return READY",
                    "verification": {"kind": "exact_text", "expected_text": "READY"},
                },
                {
                    "request_id": "verify-python", "prompt": "Write Python code for add",
                    "verification": {
                        "kind": "python_tests", "bundle_id": "add-v1",
                        "test_source": "assert add(2, 3) == 5\nassert add(-1, 1) == 0",
                    },
                },
                {
                    "request_id": "verify-retrieval", "prompt": "Where does FAM_OS run?",
                    "verification": {
                        "kind": "retrieval_citations", "sources": [{
                            "source_id": "source-1", "locator": "memory://source-1",
                            "content": "FAM_OS runs locally.", "provenance_id": "test-v1",
                        }],
                    },
                },
                {
                    "request_id": "verify-math", "prompt": "Calculate the equation",
                    "verification": {
                        "kind": "math_equivalence", "reference_expression": "(x+1)**2",
                        "variable": "x", "sample_points": ["-2", "0", "3.5"],
                        "absolute_tolerance": "1e-40", "precision_digits": 50,
                    },
                },
                {
                    "request_id": "verify-media", "prompt": "OCR this image",
                    "verification": {
                        "kind": "media_artifact_text", "artifact_path": str(image),
                        "artifact_sha256": image_digest, "expected_text": "FAM_OS",
                        "maximum_artifact_bytes": 1024,
                    },
                },
            )
            try:
                results = tuple(_terminal(gateway, api.create(item).session_id) for item in documents)
                self.assertTrue(all(item.result.status is ResultStatus.VERIFIED for item in results))
                runs = tuple(
                    repositories.verifications.runs_for_request(item["request_id"])[0]
                    for item in documents
                )
                self.assertEqual(
                    {
                        "verifier.text.exact-v1", "python.deterministic-tests.v1",
                        "retrieval.citations.v1", "math.sympy-equivalence.v1",
                        "media.artifact-text.v1",
                    },
                    {item.verifier_id for item in runs},
                )
                self.assertTrue(all(item.effective_trust == "local_unverified" for item in runs))
                self.assertTrue(all(len(item.verified_artifact_sha256) == 64 for item in runs))
                self.assertTrue(runtime.requests[-1].messages[-1].images)
                self.assertTrue(runtime.requests[-1].json_output)
            finally:
                database.close()

    def test_python_repair_receives_full_tests_and_observed_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = _Runtime((
                "def add(left, right):\n    return left\n",
                "def add(left, right):\n    return left + right\n",
            ))
            database, repositories, gateway = _gateway(root, runtime)
            source = "assert add(2, 3) == 5\nassert add(-1, 1) == 0"
            try:
                accepted = ConsoleTaskApi(gateway).create({
                    "request_id": "verify-python-repair",
                    "prompt": "Write Python code for add",
                    "verification": {
                        "kind": "python_tests", "bundle_id": "add-v1",
                        "test_source": source,
                    },
                })
                result = _terminal(gateway, accepted.session_id)
                self.assertIs(result.result.status, ResultStatus.VERIFIED)
                self.assertEqual(2, len(runtime.requests))
                repair_prompt = runtime.requests[1].messages[-1].content
                self.assertIn(source, repair_prompt)
                self.assertIn("Deterministic verifier feedback", repair_prompt)
                self.assertIn("AssertionError", repair_prompt)
                runs = repositories.verifications.runs_for_request(
                    "verify-python-repair",
                )
                self.assertEqual(["failed", "passed"], [item.status.value for item in runs])
            finally:
                database.close()


class _Runtime:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def chat(self, request):
        self.requests.append(request)
        return type("Response", (), {"content": self.responses.pop(0)})()

    def loaded_models(self):
        return ()


def _gateway(root, runtime):
    database = ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid()))
    result = SecureStorage(
        database, OwnerKeyStore(root / "master.key", os.geteuid()),
    ).open()
    composition = CoreStorageComposition(database, result.cipher, str(os.geteuid()))
    repositories = composition.repositories()
    entry = RuntimeModelEntry(
        "test:model", "economical", tuple(ModelIntent), 1024**3, 8192, "0" * 64,
        (
            "verifier.text.exact-v1", "python.deterministic-tests.v1",
            "retrieval.citations.v1", "math.sympy-equivalence.v1",
            "media.artifact-text.v1",
        ),
    )
    selector = ResourceAwareModelSelector(RuntimeModelCatalog((entry,)))
    gateway = ProductionTaskGateway(
        runtime, repositories, selector, lambda: HostCapacity(16 * 1024**3),
        composition.budget_ledger, verifier=production_verifier(repositories),
    )
    return database, repositories, gateway


def _terminal(gateway, session_id):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        snapshot = gateway.snapshot(session_id)
        if snapshot.state is ShellRunState.TERMINAL:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("verified production task did not become terminal")


if __name__ == "__main__":
    unittest.main()
