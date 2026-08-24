"""Release-owned PostgreSQL service template for natural integration."""

from fam_os.core.engineering import (
    IntegrationHealthCheck,
    IntegrationHealthKind,
    IntegrationServiceKind,
    IntegrationServiceSpec,
    IntegrationVolumeMount,
)
from fam_os.adapters.integration.natural_template_identity import (
    POSTGRESQL_HEALTH_RECIPE_ID,
    POSTGRESQL_IMAGE_REF,
    POSTGRESQL_IMAGE_SHA256,
)


POSTGRESQL_VOLUME_BYTES = 256 * 1024**2


def postgresql_service_spec(
    service_id: str,
    dependency_ids: tuple[str, ...],
    secret_refs: tuple[str, ...],
) -> IntegrationServiceSpec:
    """Map one declared role to immutable image, health, and resource policy."""

    if len(secret_refs) != 1:
        raise PermissionError(
            "natural PostgreSQL requires exactly one opaque password secret ref"
        )
    return IntegrationServiceSpec(
        service_id,
        IntegrationServiceKind.CONTAINER,
        None,
        (),
        POSTGRESQL_IMAGE_REF,
        POSTGRESQL_IMAGE_SHA256,
        (),
        (IntegrationVolumeMount(
            "postgres-data",
            "runtime/postgresql",
            "/var/lib/postgresql/data",
            False,
            POSTGRESQL_VOLUME_BYTES,
        ),),
        IntegrationHealthCheck(
            IntegrationHealthKind.SIGNED_RECIPE,
            None,
            None,
            POSTGRESQL_HEALTH_RECIPE_ID,
            1,
            1,
            30,
        ),
        dependency_ids,
        secret_refs,
    )
