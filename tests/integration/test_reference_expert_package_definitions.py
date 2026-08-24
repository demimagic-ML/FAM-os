import json
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
CAPABILITY_PREFIXES = {
    "conversation": ("language.",),
    "grounded_question": ("language.", "retrieval."),
    "read_only_task": ("language.",),
    "code": ("code.",),
    "application_mutation": ("code.",),
    "math": ("math.",),
    "retrieval": ("retrieval.",),
    "media": ("vision.",),
    "administration": ("language.",),
}


class ReferenceExpertPackageDefinitionTests(unittest.TestCase):
    def test_every_expert_has_one_exact_runtime_binding(self) -> None:
        manifests = DirectoryExpertManifestSource(PACKAGE_ROOT / "experts").load()
        bindings = tuple(
            self.load(path, ExpertRuntimeBinding)
            for path in sorted((PACKAGE_ROOT / "bindings").glob("*.json"))
        )
        self.assertEqual(20, len(manifests))
        self.assertEqual(20, len(bindings))
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
            (
                value.coordinate.package_id,
                value.coordinate.package_version,
                value.expert_id,
            ): value
            for value in (
                self.load(path, ExpertRuntimeBinding)
                for path in sorted((PACKAGE_ROOT / "bindings").glob("*.json"))
            )
        }
        selected = self.runtime_coordinates()
        strong = tuple(
            value for value in manifests
            if value.tier.value == "escalation" and self.coordinate(value) in selected
        )
        self.assertEqual(
            {"laguna-xs.2:q4_K_M", "gemma4:26b"},
            {bindings[self.coordinate(value)].artifact_ref for value in strong},
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
        strong = tuple(
            item for item in manifests
            if item.tier is ExpertTier.ESCALATION
            and self.coordinate(item) in self.runtime_coordinates()
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

    def test_runtime_catalog_verifiers_are_declared_by_bound_expert_packages(
        self,
    ) -> None:
        manifests = DirectoryExpertManifestSource(PACKAGE_ROOT / "experts").load()
        manifest_map = {
            (item.package.package_id, item.package.package_version, item.expert_id): item
            for item in manifests
        }
        available = {}
        for path in sorted((PACKAGE_ROOT / "bindings").glob("*.json")):
            binding = self.load(path, ExpertRuntimeBinding)
            coordinate = (
                binding.coordinate.package_id,
                binding.coordinate.package_version,
                binding.expert_id,
            )
            available[coordinate] = (manifest_map[coordinate], binding)
        declared = {}
        for manifest, binding in available.values():
            declared.setdefault(binding.artifact_ref, set()).update(
                manifest.required_verifier_ids,
            )
        runtime = json.loads(
            (PACKAGE_ROOT / "runtime/model-catalog.json").read_text(
                encoding="utf-8",
            )
        )

        for model in runtime["models"]:
            with self.subTest(model_ref=model["model_ref"]):
                self.assertIn(model["model_ref"], declared)
                self.assertEqual(
                    set(model.get("verifier_ids", ())),
                    declared[model["model_ref"]],
                )
                scopes = model.get("expert_scopes", ())
                expected_experts = {
                    binding.expert_id
                    for _, binding in available.values()
                    if binding.artifact_ref == model["model_ref"]
                }
                self.assertEqual(
                    expected_experts,
                    {scope["expert_id"] for scope in scopes},
                )
                self.assertEqual(
                    set(model["intents"]),
                    {intent for scope in scopes for intent in scope["intents"]},
                )
                self.assertEqual(
                    set(model.get("verifier_ids", ())),
                    {
                        verifier_id
                        for scope in scopes
                        for verifier_id in scope.get("verifier_ids", ())
                    },
                )
                for scope in scopes:
                    coordinate = (
                        scope["package_id"],
                        scope["package_version"],
                        scope["expert_id"],
                    )
                    self.assertIn(coordinate, available)
                    manifest, binding = available[coordinate]
                    self.assertEqual(model["model_ref"], binding.artifact_ref)
                    self.assertEqual(
                        set(scope.get("verifier_ids", ())),
                        set(manifest.required_verifier_ids),
                    )
                    for intent in scope["intents"]:
                        self.assertTrue(any(
                            capability.startswith(prefix)
                            for prefix in CAPABILITY_PREFIXES[intent]
                            for capability in manifest.capabilities
                        ))

    def test_both_strong_code_models_can_escalate_application_mutation(self):
        runtime = json.loads(
            (PACKAGE_ROOT / "runtime/model-catalog.json").read_text(
                encoding="utf-8",
            )
        )
        strong = {
            model["model_ref"]: model for model in runtime["models"]
            if model["model_ref"] in {"gemma4:26b", "laguna-xs.2:q4_K_M"}
        }
        self.assertEqual(
            {"gemma4:26b", "laguna-xs.2:q4_K_M"}, set(strong),
        )
        for model_ref, model in strong.items():
            with self.subTest(model_ref=model_ref):
                self.assertIn("application_mutation", model["intents"])
                self.assertTrue(all(
                    "application_mutation" in scope["intents"]
                    for scope in model["expert_scopes"]
                ))

    @staticmethod
    def load(path, expected_type):
        value = loads_document(path.read_text(encoding="utf-8"))
        if not isinstance(value, expected_type):
            raise AssertionError(f"wrong document type: {path}")
        return value

    @staticmethod
    def coordinate(manifest):
        return (
            manifest.package.package_id,
            manifest.package.package_version,
            manifest.expert_id,
        )

    @staticmethod
    def runtime_coordinates():
        runtime = json.loads(
            (PACKAGE_ROOT / "runtime/model-catalog.json").read_text(
                encoding="utf-8",
            )
        )
        return {
            (scope["package_id"], scope["package_version"], scope["expert_id"])
            for model in runtime["models"]
            for scope in model["expert_scopes"]
        }

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
