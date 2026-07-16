import unittest
from dataclasses import replace

from fam_os.supervisor import (
    SupervisorCapability,
    SupervisorNonGoal,
    SupervisorTrustScope,
    canonical_supervisor_boundary,
)


class SupervisorBoundaryTests(unittest.TestCase):
    def test_canonical_boundary_names_current_and_planned_capabilities(self) -> None:
        boundary = canonical_supervisor_boundary()
        self.assertEqual(SupervisorTrustScope.USER_SESSION, boundary.trust_scope)
        self.assertTrue(
            boundary.implements(SupervisorCapability.START_UNPRIVILEGED_SERVICE)
        )
        self.assertTrue(
            boundary.implements(SupervisorCapability.APPLY_SERVICE_RESOURCE_LIMITS)
        )
        self.assertTrue(
            boundary.implements(SupervisorCapability.GRANT_DECLARED_DEVICE_ACCESS)
        )
        self.assertTrue(
            boundary.implements(
                SupervisorCapability.EMIT_IMMUTABLE_AUDIT_EVENT
            )
        )
        self.assertTrue(
            boundary.implements(SupervisorCapability.RECOVER_FAILED_SERVICE)
        )
        self.assertTrue(
            boundary.implements(SupervisorCapability.SAFE_TERMINATE_OWNED_SERVICE)
        )
        self.assertEqual((), boundary.planned_capabilities)

    def test_non_goals_exclude_intelligence_and_broad_machine_authority(self) -> None:
        non_goals = set(canonical_supervisor_boundary().non_goals)
        self.assertEqual(set(SupervisorNonGoal), non_goals)
        self.assertIn(SupervisorNonGoal.MODEL_INFERENCE, non_goals)
        self.assertIn(SupervisorNonGoal.ROUTING_OR_PLANNING, non_goals)
        self.assertIn(SupervisorNonGoal.SYSTEM_SERVICE_ADMINISTRATION, non_goals)
        self.assertIn(SupervisorNonGoal.CREDENTIAL_OR_SECRET_MANAGEMENT, non_goals)

    def test_boundary_cannot_disable_authentication_or_admit_system_control(self) -> None:
        boundary = canonical_supervisor_boundary()
        with self.assertRaisesRegex(ValueError, "authenticated"):
            replace(boundary, authenticated_caller_required=False)
        with self.assertRaisesRegex(ValueError, "system control"):
            replace(boundary, system_service_control_allowed=True)
        with self.assertRaisesRegex(ValueError, "model logic"):
            replace(boundary, model_logic_allowed=True)

    def test_current_and_planned_capabilities_cannot_overlap(self) -> None:
        boundary = canonical_supervisor_boundary()
        with self.assertRaisesRegex(ValueError, "disjoint"):
            replace(
                boundary,
                planned_capabilities=(boundary.implemented_capabilities[0],),
            )


if __name__ == "__main__":
    unittest.main()
