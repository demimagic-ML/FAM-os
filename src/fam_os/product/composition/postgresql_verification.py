"""Optional physical composition for isolated PostgreSQL verification."""

from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.database import (
    NaturalPostgreSQLVerificationPlanBuilder,
    PostgreSQLIntegrationVerificationAdapter,
)
from fam_os.adapters.integration import DockerCommandClient
from fam_os.core.engineering import PostgreSQLIntegrationVerificationService
from fam_os.product.composition.database_engineering import (
    ProductDatabaseBackupProtector,
)


@dataclass(frozen=True, slots=True)
class PostgreSQLVerificationUnit:
    planner: NaturalPostgreSQLVerificationPlanBuilder
    service: object
    available: bool


def compose_postgresql_verification(
    owner_id,
    cipher,
    authorizer,
    docker_executable: Path = Path("/usr/bin/docker"),
) -> PostgreSQLVerificationUnit:
    planner = NaturalPostgreSQLVerificationPlanBuilder()
    try:
        client = DockerCommandClient(
            docker_executable,
            maximum_output_bytes=64 * 1024 * 1024,
        )
    except (OSError, PermissionError):
        return PostgreSQLVerificationUnit(
            planner, UnavailablePostgreSQLVerificationService(), False,
        )
    protector = ProductDatabaseBackupProtector(
        owner_id, cipher, "postgresql-custom-dump",
    )
    return PostgreSQLVerificationUnit(
        planner,
        PostgreSQLIntegrationVerificationService(
            authorizer,
            PostgreSQLIntegrationVerificationAdapter(protector, client),
        ),
        True,
    )


class UnavailablePostgreSQLVerificationService:
    def execute(self, *args, **kwargs):
        raise RuntimeError(
            "installed PostgreSQL verification runtime is unavailable"
        )
