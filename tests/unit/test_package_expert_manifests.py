import unittest

from fam_os.experts import (
    EXPERT_CAPABILITY_NAMESPACE_VERSION,
    EXPERT_MANIFEST_CONTRACT_VERSION,
    ExpertManifest,
    ExpertManifestV1Alpha1,
    ExpertResourceRequirements,
    ExpertTier,
    capability_satisfies,
    migrate_expert_manifest_v1alpha1,
    parse_expert_capability_id,
)
from fam_os.registry import ArtifactDigest, PackageMetadata, PackageTrustLevel


def _package(**overrides: object) -> PackageMetadata:
    values = {
        "package_id": "fam.expert.code-economical",
        "package_version": "1.0.0",
        "publisher_id": "fam-project",
        "license_id": "Apache-2.0",
        "trust_level": PackageTrustLevel.SIGNED,
        "artifact_digest": ArtifactDigest("sha256", "a" * 64),
        "signature_key_id": "fam-release-key-1",
    }
    values.update(overrides)
    return PackageMetadata(**values)


def _manifest(**overrides: object) -> ExpertManifest:
    values = {
        "package": _package(),
        "expert_id": "expert.code.economical",
        "display_name": "Economical code expert",
        "tier": ExpertTier.ECONOMICAL,
        "capabilities": ("code.generate.python", "code.repair.python"),
        "runtime_contract_id": "fam.inference.chat/v1",
        "artifact_ids": ("weights.primary", "prompt.system"),
        "resources": ExpertResourceRequirements(
            estimated_resident_bytes=6_700_000_000,
            storage_bytes=5_000_000_000,
            max_context_tokens=8_192,
            minimum_system_memory_bytes=8 * 1024**3,
            supported_architectures=("x86_64", "aarch64"),
        ),
        "required_verifier_ids": ("verifier.python.tests",),
    }
    values.update(overrides)
    return ExpertManifest(**values)


class PackageMetadataTests(unittest.TestCase):
    def test_signed_package_identifies_license_digest_and_signer(self) -> None:
        package = _package()
        self.assertEqual(package.license_id, "Apache-2.0")
        self.assertEqual(package.artifact_digest.algorithm, "sha256")
        self.assertEqual(package.signature_key_id, "fam-release-key-1")

    def test_signed_package_requires_signature_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "require signature_key_id"):
            _package(signature_key_id=None)

    def test_unverified_package_cannot_claim_signer(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot claim"):
            _package(trust_level=PackageTrustLevel.LOCAL_UNVERIFIED)


class ExpertManifestTests(unittest.TestCase):
    def test_declares_capability_resources_license_trust_and_verifier(self) -> None:
        manifest = _manifest()
        self.assertEqual(manifest.contract_version, EXPERT_MANIFEST_CONTRACT_VERSION)
        self.assertEqual(manifest.resources.max_context_tokens, 8_192)
        self.assertEqual(manifest.required_verifier_ids, ("verifier.python.tests",))
        self.assertNotIn("ollama", manifest.runtime_contract_id.lower())

    def test_rejects_duplicate_capabilities(self) -> None:
        with self.assertRaisesRegex(ValueError, "capabilities values must be unique"):
            _manifest(capabilities=("code.generate.python", "code.generate.python"))

    def test_uses_canonical_exact_match_capability_namespace(self) -> None:
        parsed = parse_expert_capability_id("code.generate.python")
        self.assertEqual(EXPERT_CAPABILITY_NAMESPACE_VERSION, "fam.expert.capabilities/v1")
        self.assertEqual((parsed.domain, parsed.operation), ("code", "generate"))
        self.assertTrue(capability_satisfies("code.generate.python", "code.generate.python"))
        self.assertFalse(capability_satisfies("code.generate.python", "code.generate"))

    def test_migrates_legacy_manifest_explicitly(self) -> None:
        current = _manifest()
        legacy = ExpertManifestV1Alpha1(
            current.package,
            current.expert_id,
            current.display_name,
            current.tier,
            current.capabilities,
            current.runtime_contract_id,
            current.artifact_ids,
            current.resources,
            current.required_verifier_ids,
        )
        migrated = migrate_expert_manifest_v1alpha1(legacy)
        self.assertEqual(migrated.capabilities, legacy.capabilities)
        self.assertEqual(migrated.contract_version, EXPERT_MANIFEST_CONTRACT_VERSION)

    def test_migration_rejects_noncanonical_legacy_capability(self) -> None:
        current = _manifest()
        legacy = ExpertManifestV1Alpha1(
            current.package,
            current.expert_id,
            current.display_name,
            current.tier,
            ("historical-unknown",),
            current.runtime_contract_id,
            current.artifact_ids,
            current.resources,
        )
        with self.assertRaisesRegex(ValueError, "unknown expert capability domain"):
            migrate_expert_manifest_v1alpha1(legacy)

    def test_rejects_unknown_or_noncanonical_capability_domains(self) -> None:
        for capability in ("unknown.generate", "Code.generate", " code.generate"):
            with self.subTest(capability=capability):
                with self.assertRaises(ValueError):
                    _manifest(capabilities=(capability,))

    def test_vendor_capability_is_bound_to_package_publisher(self) -> None:
        capability = "vendor.fam-project.special.reason"
        self.assertEqual(_manifest(capabilities=(capability,)).capabilities, (capability,))
        with self.assertRaisesRegex(ValueError, "publisher"):
            _manifest(capabilities=("vendor.someone-else.special.reason",))

    def test_required_accelerator_has_vram_minimum(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive accelerator memory"):
            ExpertResourceRequirements(
                estimated_resident_bytes=1,
                storage_bytes=1,
                max_context_tokens=1,
                accelerator_optional=False,
            )

    def test_requires_supported_contract_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "contract_version"):
            _manifest(contract_version="fam.expert.manifest/v2")


if __name__ == "__main__":
    unittest.main()
