import unittest

from fam_os.applications import (
    CapabilityRegistryEntry, WORKSPACE_MAP_CAPABILITY,
    WORKSPACE_PATCH_CAPABILITY, WORKSPACE_RETRIEVE_CAPABILITY,
)
from fam_os.core.production.application_plan_compiler import ApplicationPlanCompiler
from fam_os.product.composition.owner_workspace_capabilities import workspace_descriptors
from fam_os.routing import RouteDecision, RouteName
from tests.contract.schema_application_fixtures import registry_entry


class ApplicationPlanCompilerTests(unittest.TestCase):
    def test_action_capability_produces_preview_approval_execution_and_verification(self):
        entry = registry_entry()
        capabilities = ("core.intent.application_mutation", entry.capability_id)
        route = RouteDecision(RouteName.CODE, 1.0, "Application mutation", capabilities)
        plan = ApplicationPlanCompiler().compile("request-1", route, (entry,), False)
        self.assertTrue(plan.verification_required)
        self.assertEqual(
            ["inference", "prepare_action", "confirm_action", "execute_action"],
            [step.kind.value for step in plan.steps[:4]],
        )
        self.assertEqual(entry.capability.postcondition_ids, plan.steps[3].acceptance_ids)
        self.assertEqual(entry.capability.postcondition_ids, plan.steps[4].acceptance_ids)

    def test_workspace_patch_reobserves_retrieved_files_before_verification(self):
        descriptors = workspace_descriptors()
        entries = tuple(
            CapabilityRegistryEntry(
                f"entry-{item.capability_id}", "owner-filesystem",
                "owner-filesystem", "fam.local.filesystem", item,
            )
            for item in descriptors
            if item.capability_id in {
                WORKSPACE_MAP_CAPABILITY, WORKSPACE_RETRIEVE_CAPABILITY,
                WORKSPACE_PATCH_CAPABILITY,
            }
        )
        route = RouteDecision(
            RouteName.CODE, 1.0, "Workspace mutation",
            (
                "core.intent.application_mutation",
                *(item.capability_id for item in entries),
            ),
        )

        plan = ApplicationPlanCompiler().compile(
            "workspace-request", route, entries, False,
        )

        self.assertEqual(
            [
                "observe", "observe", "inference", "prepare_action",
                "confirm_action", "execute_action", "observe", "verify",
            ],
            [step.kind.value for step in plan.steps[:8]],
        )
        self.assertEqual(
            (WORKSPACE_RETRIEVE_CAPABILITY,), plan.steps[6].capability_ids,
        )


if __name__ == "__main__":
    unittest.main()
