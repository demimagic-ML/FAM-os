import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fam_os.adapters.integration import DockerCommandClient
from fam_os.adapters.integration.docker_environment import (
    DockerIntegrationEnvironmentAdapter,
)
from fam_os.core.engineering import EngineeringAuthority, IntegrationHealthKind
from tests.contract.schema_integration_environment_fixtures import (
    NOW,
    integration_environment_schema_values,
)


POSTGRES_IMAGE = "postgres:17-alpine"
POSTGRES_SHA256 = "742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193"


class PostgresSecrets:
    def environment(self, secret_refs, consumer_id):
        if secret_refs != ("secret.postgres-test",):
            raise PermissionError("unexpected test secret reference")
        return {
            "POSTGRES_PASSWORD": "bounded-integration-password",
        }


class LiveControl:
    def cancelled(self):
        return False

    def authorization_active(self):
        return True


class PostgresHealthRecipes:
    def __init__(self, client):
        self.client = client

    def healthy(self, signed_recipe_id, runtime_id, timeout_seconds):
        if signed_recipe_id != "integration.postgres.pg-isready.v1":
            raise PermissionError("untrusted health recipe")
        result = self.client.run((
            "exec", runtime_id, "pg_isready", "--quiet",
            "--username", "postgres", "--dbname", "postgres",
        ), timeout_seconds=timeout_seconds)
        if result.exit_code != 0:
            state = self.client.run((
                "inspect", "--format", "{{.State.Status}}:{{.State.Error}}",
                runtime_id,
            ))
            if not state.output.startswith(b"running:"):
                logs = self.client.run(("logs", "--tail", "40", runtime_id))
                raise RuntimeError(
                    "PostgreSQL container exited before health: "
                    + state.output.decode("utf-8", "replace").strip()
                    + " logs=" + logs.output.decode("utf-8", "replace").strip()
                )
        return result.exit_code == 0


class RealDockerIntegrationEnvironmentTests(unittest.TestCase):
    def test_cached_postgres_is_digest_pinned_healthy_bounded_and_cleaned(self):
        client = DockerCommandClient()
        observed = client.run((
            "image", "inspect", "--format", "{{.Id}}", POSTGRES_IMAGE,
        ))
        if observed.exit_code != 0:
            self.skipTest("cached PostgreSQL image is unavailable")
        self.assertEqual(f"sha256:{POSTGRES_SHA256}", observed.output.decode().strip())
        service, plan, permit, _receipt, _result = integration_environment_schema_values()
        volume = replace(service.volumes[0], maximum_bytes=268_435_456)
        health = replace(
            service.health_check, kind=IntegrationHealthKind.SIGNED_RECIPE,
            port_name=None, path=None,
            signed_recipe_id="integration.postgres.pg-isready.v1",
            interval_seconds=1, timeout_seconds=1, maximum_attempts=30,
        )
        service = replace(
            service, image_ref=POSTGRES_IMAGE, image_sha256=POSTGRES_SHA256,
            launch_arguments=(), ports=(), volumes=(volume,), health_check=health,
            secret_refs=("secret.postgres-test",),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            impact = replace(plan.resource_impact, max_processes=64)
            plan = replace(
                plan, candidate_root=str(root), services=(service,),
                retained_artifact_paths=(), maximum_memory_bytes=536_870_912,
                maximum_cpu_millis_per_second=1000,
                resource_impact=impact,
                required_authorities=(
                    EngineeringAuthority.EXECUTE,
                    EngineeringAuthority.SECRET_USE,
                ),
            )
            adapter = DockerIntegrationEnvironmentAdapter(
                PostgresSecrets(), client, lambda: NOW, lambda: "receipt-real-1",
                health_recipes=PostgresHealthRecipes(client),
            )
            receipt = adapter.launch(plan, root, permit, LiveControl())
            try:
                self.assertEqual(POSTGRES_SHA256, receipt.services[0].image_sha256)
                self.assertEqual((), receipt.services[0].allocated_ports)
                metadata = client.run((
                    "inspect", "--format", "{{json .Config.Env}}",
                    receipt.services[0].runtime_id,
                )).output
                self.assertNotIn(b"bounded-integration-password", metadata)
                self.assertIn(b"POSTGRES_PASSWORD_FILE=/run/fam-secrets/", metadata)
                self.assertEqual(
                    [], list((root / ".fam" / "secret-injection").glob("service-*")),
                )
            finally:
                restarted = DockerIntegrationEnvironmentAdapter(
                    PostgresSecrets(), client, lambda: NOW,
                    lambda: "receipt-reconciled-1",
                    health_recipes=PostgresHealthRecipes(client),
                )
                cleaned = restarted.reconcile(plan, root, permit)
            self.assertEqual("cleaned", cleaned.status.value)
            containers = client.run((
                "ps", "--all", "--quiet", "--filter",
                f"label=fam.environment={plan.environment_id}",
            ))
            self.assertEqual(b"", containers.output.strip())


if __name__ == "__main__":
    unittest.main()
