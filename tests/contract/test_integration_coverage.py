import unittest
from pathlib import Path

from fam_os.product.integration_coverage import (
    IntegrationMaturity,
    IntegrationProgramStatus,
    load_integration_coverage,
)


ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "configs/integration/coverage.json"
REQUIRED_SUBSYSTEMS = {
    "governance", "installed_service", "core", "expert_fabric", "scheduler",
    "verification", "applications", "vscode", "mcp", "ui", "memory",
    "adaptation", "multi_device", "expert_factory", "supervisor",
    "product_updates", "security", "reliability", "test_environment",
    "engineering_authority.observe", "engineering_authority.propose",
    "engineering_authority.modify", "engineering_authority.execute",
    "engineering_authority.network", "engineering_authority.publish",
    "engineering_authority.raw_shell", "engineering_authority.host_admin",
    "engineering_authority.secret_use", "engineering_authority.global_install",
    "engineering_authority.production_mutate", "engineering_authority.policy_change",
    "engineering_authority.protected_ref_write", "engineering_authority.self_update",
    "engineering_candidate_workspace", "engineering_integration_environment",
}


class IntegrationCoverageTests(unittest.TestCase):
    def test_manifest_covers_every_final_integration_subsystem(self) -> None:
        manifest = load_integration_coverage(MANIFEST)
        self.assertEqual(IntegrationProgramStatus.INTEGRATION_INCOMPLETE, manifest.program_status)
        self.assertEqual(REQUIRED_SUBSYSTEMS, {item.subsystem_id for item in manifest.items})

    def test_manifest_does_not_overstate_acceptance_evidence(self) -> None:
        manifest = load_integration_coverage(MANIFEST)
        for item in manifest.items:
            with self.subTest(subsystem=item.subsystem_id):
                self.assertEqual(IntegrationMaturity.OPERATIONALLY_PROVEN, item.target_maturity)
                if item.maturity is IntegrationMaturity.ACCEPTANCE_ONLY:
                    self.assertFalse(item.production_reachable)
                    self.assertFalse(item.installed_evidence)

    def test_engineering_authority_maturity_matches_direct_installed_evidence(self) -> None:
        manifest = load_integration_coverage(MANIFEST)
        engineering = {
            item.subsystem_id.removeprefix("engineering_authority."): item
            for item in manifest.items
            if item.subsystem_id.startswith("engineering_authority.")
        }
        self.assertEqual(
            {
                "observe", "propose", "modify", "execute", "network", "publish",
                "raw_shell", "host_admin", "secret_use", "global_install",
                "production_mutate", "policy_change", "protected_ref_write",
                "self_update",
            },
            set(engineering),
        )
        installed = {"observe", "propose", "modify", "execute"}
        for name, item in engineering.items():
            if name in installed:
                self.assertEqual(IntegrationMaturity.INSTALLED_TESTED, item.maturity)
                self.assertTrue(item.production_reachable)
                self.assertTrue(item.installed_evidence)
                self.assertIn(
                    "artifacts/product/phase30/"
                    "natural-local-delivery-20260719-02/evidence.json",
                    item.evidence_refs,
                )
            else:
                self.assertEqual(IntegrationMaturity.COMPONENT_TESTED, item.maturity)
                self.assertFalse(item.production_reachable)
                self.assertFalse(item.installed_evidence)

    def test_candidate_workspace_uses_direct_installed_natural_evidence(self) -> None:
        manifest = load_integration_coverage(MANIFEST)
        candidate = {
            item.subsystem_id: item for item in manifest.items
        }["engineering_candidate_workspace"]

        self.assertEqual(IntegrationMaturity.INSTALLED_TESTED, candidate.maturity)
        self.assertTrue(candidate.production_reachable)
        self.assertTrue(candidate.installed_evidence)

    def test_every_evidence_reference_resolves_inside_the_repository(self) -> None:
        manifest = load_integration_coverage(MANIFEST)
        for item in manifest.items:
            for reference in item.evidence_refs:
                with self.subTest(subsystem=item.subsystem_id, reference=reference):
                    path = ROOT / reference
                    self.assertTrue(path.exists(), f"missing coverage evidence: {reference}")

    def test_completed_factory_is_not_reported_as_a_component_demo(self) -> None:
        manifest = load_integration_coverage(MANIFEST)
        items = {item.subsystem_id: item for item in manifest.items}
        factory = items["expert_factory"]
        self.assertEqual(IntegrationMaturity.OPERATIONALLY_PROVEN, factory.maturity)
        self.assertTrue(factory.production_reachable)
        self.assertTrue(factory.installed_evidence)

    def test_scheduler_status_includes_the_completed_policy_and_residency_work(self) -> None:
        manifest = load_integration_coverage(MANIFEST)
        items = {item.subsystem_id: item for item in manifest.items}
        scheduler = items["scheduler"]
        references = set(scheduler.evidence_refs)
        self.assertIn("handoffs/0172-production-resource-policy-wiring.md", references)
        self.assertIn("handoffs/0173-production-residency-and-confirmed-eviction.md", references)

    def test_corrected_expert_scopes_wait_for_installed_candidate_evidence(self) -> None:
        manifest = load_integration_coverage(MANIFEST)
        expert_fabric = {
            item.subsystem_id: item for item in manifest.items
        }["expert_fabric"]

        self.assertEqual(
            IntegrationMaturity.PRODUCTION_WIRED, expert_fabric.maturity,
        )
        self.assertTrue(expert_fabric.production_reachable)
        self.assertTrue(expert_fabric.installed_evidence)
        self.assertIn(
            "handoffs/0181-verifier-compatible-expert-scoped-runtime-routing.md",
            expert_fabric.evidence_refs,
        )
        self.assertTrue(expert_fabric.known_gaps)

    def test_clean_artifact_matrix_is_recorded_without_claiming_installed_exit(self) -> None:
        manifest = load_integration_coverage(MANIFEST)
        items = {item.subsystem_id: item for item in manifest.items}
        environment = items["test_environment"]
        self.assertEqual(IntegrationMaturity.ACCEPTANCE_ONLY, environment.maturity)
        self.assertFalse(environment.production_reachable)
        self.assertFalse(environment.installed_evidence)
        self.assertIn(
            "artifacts/product/phase23/profile-matrix/"
            "phase23-required-20260718-01/profile-matrix.json",
            environment.evidence_refs,
        )


if __name__ == "__main__":
    unittest.main()
