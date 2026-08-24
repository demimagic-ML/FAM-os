import unittest
from dataclasses import replace

from fam_os.adapters.integration.environment_router import IntegrationEnvironmentExecutorRouter
from fam_os.core.engineering import IntegrationServiceKind
from tests.contract.schema_integration_environment_fixtures import integration_environment_schema_values


class Backend:
    def __init__(self, name): self.name = name
    def launch(self, *arguments): return self.name
    def cleanup(self, *arguments): return self.name
    def reconcile(self, *arguments): return self.name


class IntegrationEnvironmentRouterTests(unittest.TestCase):
    def test_homogeneous_backends_are_selected_without_core_provider_knowledge(self):
        service, plan, permit, receipt, _result = integration_environment_schema_values()
        router = IntegrationEnvironmentExecutorRouter(
            docker=Backend("docker"), process=Backend("process"),
        )
        self.assertEqual("docker", router.launch(plan, None, permit, None))
        process_service = replace(
            service, kind=IntegrationServiceKind.PROCESS,
            signed_launch_recipe_id="service@1", launch_arguments=("--serve",),
            image_ref=None, image_sha256=None, volumes=(),
        )
        process_plan = replace(plan, services=(process_service,))
        self.assertEqual("process", router.cleanup(process_plan, receipt, None, permit))

    def test_mixed_requires_both_backends_and_absent_backend_fails_closed(self):
        service, plan, permit, _receipt, _result = integration_environment_schema_values()
        process_service = replace(
            service, service_id="api", kind=IntegrationServiceKind.API,
            signed_launch_recipe_id="api@1", launch_arguments=("--serve",),
            image_ref=None, image_sha256=None, volumes=(),
        )
        mixed = replace(
            plan, services=(service, process_service),
            resource_impact=replace(plan.resource_impact, max_processes=2),
        )
        router = IntegrationEnvironmentExecutorRouter(docker=Backend("docker"))
        with self.assertRaisesRegex(PermissionError, "both executors"):
            router.launch(mixed, None, permit, None)
        with self.assertRaisesRegex(PermissionError, "unavailable"):
            router.launch(replace(plan, services=(process_service,)), None, permit, None)


if __name__ == "__main__": unittest.main()
