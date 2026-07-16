import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.filesystem import DirectoryExpertManifestSource
from fam_os.experts import (
    ExpertCompatibilityStatus,
    ExpertPackageCoordinate,
    ExpertRuntimeBinding,
    ExpertTier,
    InstalledExpertCandidateResolver,
    LocalExpertRegistry,
    validate_runtime_binding,
)
from fam_os.registry import ArtifactDigest, PackageTrustLevel, PackageTrustPolicy
from fam_os.registry.lifecycle_contracts import (
    ExpertPackageInstallationState,
    InstalledExpertPackage,
    PackageLifecycleAction,
    PackageLifecycleEvent,
)
from fam_os.schemas import loads_document
from fam_os.verification import VerifierManifest


ROOT = Path(__file__).parents[2]
PACKAGE_ROOT = ROOT / "configs" / "packages"


class ReferenceExpertPackageDefinitionTests(unittest.TestCase):
    def test_every_expert_has_one_exact_runtime_binding(self) -> None:
        manifests = DirectoryExpertManifestSource(PACKAGE_ROOT / "experts").load()
        bindings = tuple(
            self.load(path, ExpertRuntimeBinding)
            for path in sorted((PACKAGE_ROOT / "bindings").glob("*.json"))
        )
        self.assertEqual(7, len(manifests))
        self.assertEqual(7, len(bindings))
        by_coordinate = {binding.coordinate: binding for binding in bindings}
        for manifest in manifests:
            coordinate = (
                manifest.package.package_id,
                manifest.package.package_version,
            )
            binding = next(
                value for value in bindings
                if (value.coordinate.package_id, value.coordinate.package_version) == coordinate
            )
            validate_runtime_binding(manifest, binding)

    def test_strong_models_are_exact_non_default_escalation_tiers(self) -> None:
        manifests = DirectoryExpertManifestSource(PACKAGE_ROOT / "experts").load()
        bindings = {
            value.expert_id: value
            for value in (
                self.load(path, ExpertRuntimeBinding)
                for path in sorted((PACKAGE_ROOT / "bindings").glob("*.json"))
            )
        }
        strong = tuple(value for value in manifests if value.tier.value == "escalation")
        self.assertEqual(
            {"laguna-xs.2:q4_K_M", "gemma4:26b"},
            {bindings[value.expert_id].artifact_ref for value in strong},
        )
        strong_ids = {value.expert_id for value in strong}
        self.assertTrue(
            all(value.tier.value != "escalation" for value in manifests if value.expert_id not in strong_ids)
        )

    def test_verifier_and_explicit_local_development_trust_are_strict_documents(self) -> None:
        verifier = self.load(
            PACKAGE_ROOT / "verifiers" / "python-stable-toposort-v2.json",
            VerifierManifest,
        )
        policy = self.load(
            PACKAGE_ROOT / "trust" / "local-workstation-development.json",
            PackageTrustPolicy,
        )
        self.assertEqual(("stable-toposort-v2",), verifier.acceptance_ids)
        self.assertTrue(policy.allow_local_unverified)
        self.assertIn("LicenseRef-Meta-Llama-3.2", policy.allowed_license_expressions)
        self.assertNotIn("LicenseRef-Gemma-Terms", policy.allowed_license_expressions)

    def test_declared_capability_resolves_both_enabled_escalation_packages(self) -> None:
        manifests = DirectoryExpertManifestSource(PACKAGE_ROOT / "experts").load()
        bindings = tuple(
            self.load(path, ExpertRuntimeBinding)
            for path in sorted((PACKAGE_ROOT / "bindings").glob("*.json"))
        )
        strong_versions = tuple(item for item in manifests if item.tier is ExpertTier.ESCALATION)
        strong = tuple(
            max(
                (item for item in strong_versions if item.expert_id == expert_id),
                key=lambda item: item.package.package_version,
            )
            for expert_id in sorted({item.expert_id for item in strong_versions})
        )
        installed = tuple(self.installed(item) for item in strong)
        now = datetime(2026, 7, 16, tzinfo=timezone.utc)
        event = PackageLifecycleEvent(
            "install-batch", 1, now, PackageLifecycleAction.INSTALL,
            installed[0].coordinate, None, installed[0].coordinate, "committed",
        )
        state = ExpertPackageInstallationState(1, installed, (), (event,))
        registry = LocalExpertRegistry()
        registry.refresh(manifests)
        candidates = InstalledExpertCandidateResolver(registry, bindings).resolve(
            "code.generate.python", state, ExpertTier.ESCALATION
        )
        self.assertEqual(
            {"gemma4:26b", "laguna-xs.2:q4_K_M"},
            {item.runtime_binding.artifact_ref for item in candidates},
        )

    @staticmethod
    def load(path, expected_type):
        value = loads_document(path.read_text(encoding="utf-8"))
        if not isinstance(value, expected_type):
            raise AssertionError(f"wrong document type: {path}")
        return value

    @staticmethod
    def installed(manifest):
        package = manifest.package
        return InstalledExpertPackage(
            ExpertPackageCoordinate(package.package_id, package.package_version),
            manifest.expert_id,
            f"ollama-model:{manifest.expert_id}",
            package.artifact_digest,
            ArtifactDigest("sha256", "f" * 64),
            PackageTrustLevel.LOCAL_UNVERIFIED,
            "local-workstation-development",
            ExpertCompatibilityStatus.COMPATIBLE,
            "full-reference-workstation",
            datetime(2026, 7, 16, tzinfo=timezone.utc),
            True,
        )


if __name__ == "__main__":
    unittest.main()
