import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.integration.docker_client import DockerCommandResult
from fam_os.product.composition.integration_environment import (
    POSTGRES_HEALTH_RECIPE_ID,
    DenyingDockerSecretInjector,
    ProductDockerHealthRecipes,
    compose_integration_environment,
)


class UnusedAuthorizer:
    def authorize(self, request):
        raise AssertionError("not used during composition")


class RecordingClient:
    def __init__(self):
        self.calls = []

    def run(self, arguments, **kwargs):
        self.calls.append((arguments, kwargs))
        return DockerCommandResult(0, b"")


class IntegrationEnvironmentCompositionTests(unittest.TestCase):
    def test_real_trusted_docker_composes_core_service(self):
        unit = compose_integration_environment(UnusedAuthorizer())
        self.assertIsNotNone(unit)
        self.assertIsNotNone(unit.service)
        self.assertIsNotNone(unit.adapter)

    def test_product_composes_mixed_orchestrator_when_both_backends_exist(self):
        unit = compose_integration_environment(
            UnusedAuthorizer(), process_recipes=object(),
        )
        self.assertIsNotNone(unit.adapter.docker)
        self.assertIsNotNone(unit.adapter.process)
        self.assertIsNotNone(unit.adapter.mixed)

    def test_missing_or_untrusted_docker_degrades_to_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "docker"
            self.assertIsNone(compose_integration_environment(
                UnusedAuthorizer(), docker_executable=missing,
            ))
            missing.write_text("#!/bin/false\n", encoding="utf-8")
            missing.chmod(0o755)
            self.assertIsNone(compose_integration_environment(
                UnusedAuthorizer(), docker_executable=missing,
            ))

    def test_default_secret_policy_denies_and_health_recipe_is_exact(self):
        secrets = DenyingDockerSecretInjector()
        self.assertEqual({}, secrets.environment((), "consumer"))
        with self.assertRaises(PermissionError):
            secrets.environment(("secret.test",), "consumer")
        client = RecordingClient()
        recipes = ProductDockerHealthRecipes(client)
        self.assertTrue(recipes.healthy(
            POSTGRES_HEALTH_RECIPE_ID, "runtime-1", 2,
        ))
        self.assertEqual("pg_isready", client.calls[0][0][2])
        with self.assertRaises(PermissionError):
            recipes.healthy("model.recipe", "runtime-1", 2)


if __name__ == "__main__":
    unittest.main()
