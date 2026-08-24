"""Stable opaque-secret consumer identities across integration phases."""

from fam_os.adapters.integration.natural_template_identity import (
    POSTGRESQL_IMAGE_REF,
    POSTGRESQL_IMAGE_SHA256,
    POSTGRESQL_SECRET_CONSUMER_ID,
    PYTHON_API_RECIPE_ID,
    PYTHON_API_SECRET_CONSUMER_ID,
)


_PHASE_SUFFIXES = ("-candidate", "-postapply")


def integration_secret_consumer_id(service) -> str:
    """Return one provisionable consumer for candidate and post-apply runs."""

    if service.signed_launch_recipe_id == PYTHON_API_RECIPE_ID:
        return PYTHON_API_SECRET_CONSUMER_ID
    if (
        service.image_ref == POSTGRESQL_IMAGE_REF
        and service.image_sha256 == POSTGRESQL_IMAGE_SHA256
    ):
        return POSTGRESQL_SECRET_CONSUMER_ID
    service_id = getattr(service, "service_id", None)
    if not isinstance(service_id, str) or not service_id.strip():
        raise ValueError("integration secret service identity is invalid")
    logical_id = service_id
    for suffix in _PHASE_SUFFIXES:
        if logical_id.endswith(suffix):
            logical_id = logical_id[:-len(suffix)]
            break
    if not logical_id:
        raise ValueError("integration secret service identity is invalid")
    return f"integration:{logical_id}"
