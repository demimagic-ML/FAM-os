import base64
import hashlib
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.crypto import Ed25519PackageSignatureVerifier
from fam_os.adapters.filesystem import (
    ImmutablePackageArtifactStore,
    JsonPackageLifecycleStateStore,
)
from fam_os.expert_factory import (
    ConversionOutputType,
    build_specialist_release_lineage,
)
from fam_os.experts import ExpertCompatibilityEvaluator
from fam_os.product.factory_specialist_packaging import FactorySpecialistPackager
from fam_os.registry import (
    PackageTrustPolicy,
    PublisherKeyStatus,
    SignatureAlgorithm,
    TrustedPublisherKey,
)
from fam_os.registry.lifecycle import ExpertPackageLifecycle
from fam_os.registry.validation import ExpertPackageValidator
from tests.contract.schema_manifest_fixtures import effective_budget, host_inventory


NOW = datetime(2026, 7, 18, tzinfo=UTC)


class FactorySpecialistPackagingTests(unittest.TestCase):
    def test_bundle_is_signed_validated_and_installed_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            conversion = _conversion(root)
            key = Ed25519PrivateKey.from_private_bytes(b"p" * 32)
            packager, state = _packager(root, key)
            packaged = packager.package(_lineage(conversion), conversion)
            self.assertTrue(packaged.bundle_path.is_file())
            self.assertTrue(packaged.signature.signature_bytes())
            installed = state.load().packages
            self.assertEqual(1, len(installed))
            self.assertFalse(installed[0].enabled)
            self.assertTrue(packaged.receipt.installed_disabled)
            self.assertEqual(
                packaged.manifest.package.artifact_digest.value,
                hashlib.sha256(packaged.bundle_path.read_bytes()).hexdigest(),
            )

    def test_same_inputs_produce_identical_runtime_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            conversion = _conversion(root)
            lineage = _lineage(conversion)
            key = Ed25519PrivateKey.from_private_bytes(b"p" * 32)
            first, _ = _packager(root / "first", key)
            second, _ = _packager(root / "second", key)
            one = first.package(lineage, conversion)
            two = second.package(lineage, conversion)
            self.assertEqual(one.bundle_path.read_bytes(), two.bundle_path.read_bytes())

    def test_changed_conversion_output_is_rejected_before_install(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            conversion = _conversion(root)
            lineage = _lineage(conversion)
            (conversion / "adapter.gguf").write_bytes(b"tampered")
            packager, state = _packager(
                root, Ed25519PrivateKey.from_private_bytes(b"p" * 32),
            )
            with self.assertRaisesRegex(PermissionError, "adapter.gguf"):
                packager.package(lineage, conversion)
            self.assertEqual((), state.load().packages)


def _packager(root: Path, key: Ed25519PrivateKey):
    state = JsonPackageLifecycleStateStore(root / "lifecycle.json")
    lifecycle = ExpertPackageLifecycle(
        state, ImmutablePackageArtifactStore(root / "installed"),
        clock=lambda: NOW, event_id_factory=lambda: "specialist-install-1",
    )
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    policy = PackageTrustPolicy(
        "factory-specialist-policy-1", ("Apache-2.0",),
        publisher_keys=(TrustedPublisherKey(
            "factory-specialist-key-1", "fam-local-factory",
            SignatureAlgorithm.ED25519,
            base64.b64encode(public).decode(), PublisherKeyStatus.ACTIVE,
        ),),
    )
    validator = ExpertPackageValidator(
        policy, Ed25519PackageSignatureVerifier(),
    )
    packager = FactorySpecialistPackager(
        output_directory=root / "packages", lifecycle=lifecycle,
        validator=validator,
        compatibility_evaluator=ExpertCompatibilityEvaluator(),
        inventory=host_inventory(), budget=effective_budget(),
        publisher_id="fam-local-factory",
        signer_key_id="factory-specialist-key-1", signing_key=key,
        now=lambda: NOW,
    )
    return packager, state


def _conversion(root: Path) -> Path:
    output = root / "conversion"
    output.mkdir(parents=True)
    (output / "base.gguf").write_bytes(b"base-gguf")
    (output / "adapter.gguf").write_bytes(b"adapter-gguf")
    (output / "Modelfile").write_bytes(
        b"FROM ./base.gguf\nADAPTER ./adapter.gguf\n",
    )
    return output


def _lineage(output: Path):
    def sha(name: str) -> str:
        return hashlib.sha256((output / name).read_bytes()).hexdigest()

    return build_specialist_release_lineage(
        release_id="specialist-release-1", package_id="fam.specialist.code-1",
        package_version="1.0.0", expert_id="expert.specialist.code-1",
        training_capability_id="intent.code",
        declared_capabilities=("code.generate.python", "code.repair.python"),
        required_verifier_ids=("python.deterministic-tests.v1",),
        conversion_receipt_id="conversion-receipt-1",
        conversion_receipt_sha256="1" * 64,
        conversion_environment_sha256="2" * 64,
        comparison_decision_id="comparison-decision-1",
        comparison_decision_sha256="3" * 64,
        training_receipt_id="training-terminal-1",
        sealed_dataset_id="sealed-dataset-1",
        sealed_dataset_sha256="4" * 64,
        base_model_id="Qwen/Qwen3-1.7B", base_model_revision="5" * 40,
        base_model_files_sha256="6" * 64, adapter_sha256="7" * 64,
        base_gguf_sha256=sha("base.gguf"),
        adapter_gguf_sha256=sha("adapter.gguf"),
        modelfile_sha256=sha("Modelfile"), tokenizer_sha256="8" * 64,
        chat_template_sha256="9" * 64, merge_policy="runtime_lora_adapter",
        base_output_type=ConversionOutputType.BF16,
        adapter_output_type=ConversionOutputType.F16,
        runtime_model_ref="fam-code-specialist:canary", license_id="Apache-2.0",
        estimated_resident_bytes=2 * 1024**3, storage_bytes=2 * 1024**3,
        max_context_tokens=8192, minimum_system_memory_bytes=4 * 1024**3,
        minimum_accelerator_memory_bytes=0, accelerator_optional=True,
        supported_architectures=("x86_64",), created_at=NOW,
    )


if __name__ == "__main__":
    unittest.main()
