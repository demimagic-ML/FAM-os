"""Optional product composition for bounded Docker environments."""

from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.integration import (
    DockerCommandClient,
    DockerIntegrationEnvironmentAdapter,
    IntegrationEnvironmentExecutorRouter,
    ProcessIntegrationEnvironmentAdapter,
)
from fam_os.adapters.integration.postgresql_template import (
    POSTGRESQL_HEALTH_RECIPE_ID,
)
from fam_os.core.engineering.integration_environment_service import (
    IntegrationEnvironmentService,
)
from fam_os.product.integration_environment_api import (
    ProductIntegrationEnvironmentApi,
)


POSTGRES_HEALTH_RECIPE_ID = POSTGRESQL_HEALTH_RECIPE_ID


class DenyingDockerSecretInjector:
    def environment(self, secret_refs, consumer_id):
        if secret_refs:
            raise PermissionError("product Docker credentials are not provisioned")
        return {}


class ProductDockerHealthRecipes:
    def __init__(self, client: DockerCommandClient) -> None:
        self._client = client

    def healthy(self, signed_recipe_id, runtime_id, timeout_seconds):
        if signed_recipe_id != POSTGRESQL_HEALTH_RECIPE_ID:
            raise PermissionError("Docker health recipe is not release-owned")
        result = self._client.run((
            "exec", runtime_id, "pg_isready", "--quiet",
            "--username", "postgres", "--dbname", "postgres",
        ), timeout_seconds=timeout_seconds)
        return result.exit_code == 0


@dataclass(frozen=True, slots=True)
class IntegrationEnvironmentUnit:
    service: IntegrationEnvironmentService
    adapter: object
    api: ProductIntegrationEnvironmentApi | None = None
    recovery_outcomes: tuple[object, ...] = ()


def compose_integration_environment(
    authorizer,
    *,
    docker_executable: Path = Path("/usr/bin/docker"),
    secrets=None,
    owner_id: str | None = None,
    repository=None,
    process_recipes=None,
    lifecycle=None,
    network_broker=None,
    network_authority=None,
) -> IntegrationEnvironmentUnit | None:
    if (owner_id is None) != (repository is None):
        raise ValueError("integration owner and repository must be composed together")
    if (network_broker is None) != (network_authority is None):
        raise ValueError("integration network broker and signer must be composed together")
    docker = None
    try:
        client = DockerCommandClient(docker_executable)
    except (OSError, PermissionError):
        pass
    else:
        docker = DockerIntegrationEnvironmentAdapter(
            secrets or DenyingDockerSecretInjector(), client,
            health_recipes=ProductDockerHealthRecipes(client),
            network=network_broker,
        )
    process = None
    if process_recipes is not None:
        try:
            process = ProcessIntegrationEnvironmentAdapter(
                process_recipes, secrets=secrets or DenyingDockerSecretInjector(),
                network=network_broker,
            )
        except (OSError, PermissionError):
            pass
    if docker is None and process is None:
        return None
    adapter = IntegrationEnvironmentExecutorRouter(
        docker=docker, process=process, network=network_broker,
    )
    service = IntegrationEnvironmentService(
        authorizer, adapter, network_authority=network_authority,
    )
    if repository is None:
        return IntegrationEnvironmentUnit(service, adapter)
    api = ProductIntegrationEnvironmentApi(
        owner_id, service, adapter, repository, lifecycle,
    )
    incomplete = api.recover_incomplete()
    return IntegrationEnvironmentUnit(
        service, adapter, api, incomplete + api.reconcile_active(),
    )
