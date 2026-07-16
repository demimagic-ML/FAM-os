"""Representative configuration-layer schema values."""

from datetime import timedelta

from fam_os.scheduler import (
    AcceleratorRuntimeState,
    ComposedResourceConfiguration,
    ConfigurationCompositionRequest,
    DiscoveredResourceState,
    FULL_REFERENCE_WORKSTATION_PROFILE_ID,
    ResourcePolicy,
    ResourceRestriction,
    SchedulerDefaults,
    SessionResourceOverride,
    StorageRuntimeState,
    UserResourcePolicy,
    ValidationProfileConfiguration,
    ValidationProfileDocument,
    ValidationWorkloadMode,
    AcceleratorVisibility,
    ServiceResourceEnvelope,
    ValidationProfilePurpose,
    ValidationProfileRef,
    compose_resource_configuration,
)
from tests.contract.schema_application_fixtures import NOW
from tests.contract.schema_manifest_fixtures import GIB, host_inventory


def resource_policy(*, accelerator_allowed: bool = False) -> ResourcePolicy:
    return ResourcePolicy(
        cpu_quota_fraction=0.75,
        reserved_logical_cpu_count=2,
        memory_limit_fraction=0.8,
        memory_headroom_bytes=8 * GIB,
        max_swap_bytes=0,
        accelerator_allowed=accelerator_allowed,
        accelerator_memory_fraction=0.8 if accelerator_allowed else 0.0,
        accelerator_reserved_memory_bytes=GIB,
        storage_cache_fraction=0.5,
        storage_reserved_free_bytes=100 * GIB,
    )


def scheduler_defaults() -> SchedulerDefaults:
    return SchedulerDefaults(
        "defaults-1",
        ValidationProfileRef("safe-default", ValidationProfilePurpose.CUSTOM),
        resource_policy(),
    )


def profile_configuration() -> ValidationProfileConfiguration:
    return ValidationProfileConfiguration(
        "profile-full-1",
        ValidationProfileRef(
            FULL_REFERENCE_WORKSTATION_PROFILE_ID,
            ValidationProfilePurpose.FULL_HOST_CAPABILITY,
        ),
        resource_policy(accelerator_allowed=True),
    )


def user_policy() -> UserResourcePolicy:
    return UserResourcePolicy("user-policy-1", ResourceRestriction(max_cpu_cores=12))


def session_override() -> SessionResourceOverride:
    return SessionResourceOverride(
        "session-override-1",
        "session-1",
        NOW,
        ResourceRestriction(max_cpu_cores=8),
        NOW + timedelta(hours=1),
    )


def discovered_state() -> DiscoveredResourceState:
    return DiscoveredResourceState(
        "state-1",
        NOW,
        host_inventory(),
        4 * GIB,
        0,
        0,
        cgroup_cpu_quota_cores=20,
        cgroup_memory_limit_bytes=60 * GIB,
        accelerators=(AcceleratorRuntimeState("gpu-0", 0),),
        storage=(StorageRuntimeState("nvme-root", 5 * GIB),),
    )


def composition_request() -> ConfigurationCompositionRequest:
    return ConfigurationCompositionRequest(
        "composition-schema-1",
        scheduler_defaults(),
        discovered_state(),
        profile_configuration(),
        user_policy(),
        session_override(),
    )


def composed_configuration() -> ComposedResourceConfiguration:
    return compose_resource_configuration(composition_request())


def validation_profile_document() -> ValidationProfileDocument:
    return ValidationProfileDocument(
        "profile.full-reference-workstation.fixture",
        "Full reference workstation fixture",
        "Schema fixture for the full-host validation profile.",
        ValidationWorkloadMode.FULL_HOST,
        profile_configuration(),
        ServiceResourceEnvelope(None, 0, None, AcceleratorVisibility.DISCOVERED),
    )


def configuration_schema_values() -> tuple[object, ...]:
    return (
        scheduler_defaults(),
        profile_configuration(),
        user_policy(),
        session_override(),
        discovered_state(),
        composition_request(),
        composed_configuration(),
        validation_profile_document(),
    )
