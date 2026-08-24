import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.core.ports.inference import InferenceResponse, LoadedModel
from fam_os.expert_factory import (
    build_canary_approval,
    build_specialist_package_receipt,
)
from fam_os.product.factory_canary import (
    FactorySpecialistCanaryRunner,
    ProductFactoryCanaryApprovals,
)
from fam_os.product.factory_specialist_packaging import _build_bundle
from fam_os.telemetry import InferenceMetrics
from tests.unit.test_factory_specialist_packaging import _conversion, _lineage


NOW = datetime(2026, 7, 18, tzinfo=UTC)


class FactoryCanaryRunnerTests(unittest.TestCase):
    def test_approval_refuses_suite_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = _fixture(root)
            substituted = root / "substituted.jsonl"
            substituted.write_text(fixture.suite.read_text())
            approvals = ProductFactoryCanaryApprovals(
                fixture.repositories, suite_path=fixture.suite,
                now=lambda: NOW,
            )
            with self.assertRaisesRegex(PermissionError, "configured suite"):
                approvals.issue(
                    request_id="substitution", package_receipt_id="receipt-1",
                    suite_path=substituted, verifier_id="verifier-1",
                    maximum_output_tokens=64, maximum_wall_seconds=60,
                    maximum_ram_bytes=1024, maximum_vram_bytes=1024,
                    one_use_canary_id="canary-substitution",
                    lifetime_seconds=60, confirmed=True,
                )

    def test_verified_exact_scope_canary_signs_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = _fixture(root)
            installer = _Installer()
            runner = FactorySpecialistCanaryRunner(
                repositories=fixture.repositories,
                artifact_root=fixture.artifact_root,
                suite_path=fixture.suite, workspace_root=root / "workspaces",
                installer=installer, runtime=_Runtime(), verifier=_Verifier(True),
                signer_key_id="factory-canary-key-1",
                signing_key=Ed25519PrivateKey.from_private_bytes(b"c" * 32),
                now=lambda: NOW,
            )
            decision = runner.run(
                approval_id=fixture.approval.approval_id, confirmed=True,
            )
            self.assertTrue(decision.activate)
            self.assertEqual(1, fixture.release.claims)
            self.assertEqual(1, len(fixture.release.completed))
            self.assertEqual([], installer.removed)
            self.assertEqual([], list((root / "workspaces").iterdir()))

    def test_failed_verifier_removes_canary_model_and_signs_denial(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = _fixture(root)
            installer = _Installer()
            runner = FactorySpecialistCanaryRunner(
                repositories=fixture.repositories,
                artifact_root=fixture.artifact_root,
                suite_path=fixture.suite, workspace_root=root / "workspaces",
                installer=installer, runtime=_Runtime(), verifier=_Verifier(False),
                signer_key_id="factory-canary-key-1",
                signing_key=Ed25519PrivateKey.from_private_bytes(b"c" * 32),
                now=lambda: NOW,
            )
            decision = runner.run(
                approval_id=fixture.approval.approval_id, confirmed=True,
            )
            self.assertFalse(decision.activate)
            self.assertIn("canary.verifier_failed", decision.reason_codes)
            self.assertEqual([fixture.approval.runtime_model_ref], installer.removed)


class _Installer:
    def __init__(self) -> None:
        self.removed = []

    def create(self, model_ref, modelfile):
        if not modelfile.is_file():
            raise RuntimeError("missing Modelfile")
        return "d" * 64

    def remove(self, model_ref):
        self.removed.append(model_ref)


class _Runtime:
    def chat(self, request):
        return InferenceResponse(
            "```python\ndef stable_topological_sort(value):\n    return []\n```",
            InferenceMetrics(request.model_ref, 1, 0, 10, 10, 10),
        )

    def loaded_models(self):
        return (LoadedModel("fam-code-specialist:canary", 2 * 1024**3, 1024**3),)

    def unload(self, model_ref):
        return None

    def prewarm(self, model_ref, keep_alive="10m"):
        return None


class _Verifier:
    def __init__(self, passed):
        self._passed = passed

    def verify(self, **values):
        return self._passed


class _ReleaseRepository:
    def __init__(self, approval, lineage, package):
        self.approval = approval
        self.release_lineage = lineage
        self.package = package
        self.claims = 0
        self.completed = []

    def canary_approval(self, approval_id):
        return self.approval if approval_id == self.approval.approval_id else None

    def activation_decision(self, canary_id):
        return None

    def package_receipt_by_sha(self, sha256):
        return self.package if sha256 == self.package.receipt_sha256 else None

    def lineage(self, release_id):
        return self.release_lineage if release_id == self.release_lineage.release_id else None

    def claim_canary(self, *args):
        self.claims += 1

    def complete_canary(self, report, decision):
        self.completed.append((report, decision))


class _Repositories:
    def __init__(self, release):
        self.factory_releases = release


class _Fixture:
    pass


def _fixture(root: Path):
    conversion = _conversion(root)
    lineage = _lineage(conversion)
    artifact_root = root / "installed"
    artifact = artifact_root / "fam.specialist.code-1/1.0.0/artifact.bin"
    artifact.parent.mkdir(parents=True)
    temporary = root / "bundle.tar"
    _build_bundle(temporary, lineage, conversion)
    artifact.write_bytes(temporary.read_bytes())
    package = build_specialist_package_receipt(
        receipt_id="specialist-package-receipt-1",
        release_id=lineage.release_id, package_id=lineage.package_id,
        package_version=lineage.package_version,
        lineage_sha256=lineage.lineage_sha256, artifact_sha256="1" * 64,
        expert_manifest_sha256="2" * 64, runtime_binding_sha256="3" * 64,
        signature_sha256="4" * 64, signature_key_id="package-key-1",
        validation_policy_id="package-policy-1", compatibility_sha256="5" * 64,
        artifact_locator="fam.specialist.code-1/1.0.0/artifact.bin",
        lifecycle_revision=1, installed_disabled=True, installed_at=NOW,
    )
    suite = root / "suite.jsonl"
    suite.write_text(json.dumps({
        "case_id": "stable-toposort", "prompt": "Implement stable topological sort",
        "bundle_id": "stable-toposort-v2",
        "test_source": "assert stable_topological_sort({}) == []",
    }) + "\n")
    suite_sha = __import__("hashlib").sha256(suite.read_bytes()).hexdigest()
    approval = build_canary_approval(
        approval_id="canary-approval-1", release_id=lineage.release_id,
        package_receipt_sha256=package.receipt_sha256,
        package_id=lineage.package_id, package_version=lineage.package_version,
        expert_id=lineage.expert_id, runtime_model_ref=lineage.runtime_model_ref,
        capability_id=lineage.training_capability_id,
        verifier_id=lineage.required_verifier_ids[0], suite_sha256=suite_sha,
        case_count=1, maximum_output_tokens=512, maximum_wall_seconds=300,
        maximum_ram_bytes=16 * 1024**3, maximum_vram_bytes=15 * 1024**3,
        one_use_canary_id="canary-1", issued_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    release = _ReleaseRepository(approval, lineage, package)
    fixture = _Fixture()
    fixture.approval = approval
    fixture.release = release
    fixture.repositories = _Repositories(release)
    fixture.artifact_root = artifact_root
    fixture.suite = suite
    return fixture


if __name__ == "__main__":
    unittest.main()
