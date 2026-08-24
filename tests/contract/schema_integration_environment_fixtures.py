"""Representative bounded integration-environment schema values."""

import base64
from datetime import datetime, timedelta, timezone

from fam_os.core.engineering import (
    EngineeringAuthority,
    EngineeringResourceImpact,
    IntegrationEnvironmentPlan,
    IntegrationEnvironmentReceipt,
    IntegrationEnvironmentStatus,
    IntegrationEnvironmentStartResult,
    IntegrationExecutionPermit,
    IntegrationHealthCheck,
    IntegrationHealthKind,
    IntegrationNetworkMode,
    IntegrationPortBinding,
    IntegrationServiceKind,
    IntegrationServiceReceipt,
    IntegrationServiceSpec,
    IntegrationVolumeMount,
    integration_environment_plan_digest,
    IntegrationAllocatedPort,
    IntegrationRetainedArtifact,
    IntegrationNetworkAttachment,
    IntegrationNetworkAttachmentKind,
    IntegrationNetworkEnforcementRequest,
    IntegrationNetworkLease,
    IntegrationNetworkUsage,
    NaturalIntegrationEnvironmentDeclaration,
    NaturalIntegrationServiceDeclaration,
    NaturalIntegrationServiceTemplate,
)


NOW = datetime(2026, 7, 19, 20, 0, tzinfo=timezone.utc)


def natural_integration_declaration_schema_value():
    return NaturalIntegrationEnvironmentDeclaration(
        "full-stack-preview",
        (
            NaturalIntegrationServiceDeclaration(
                "api", NaturalIntegrationServiceTemplate.PYTHON_API, (),
            ),
            NaturalIntegrationServiceDeclaration(
                "web", NaturalIntegrationServiceTemplate.STATIC_SITE,
                ("api",),
            ),
        ),
    )


def integration_environment_schema_values() -> tuple[object, ...]:
    service = IntegrationServiceSpec(
        "postgres-1", IntegrationServiceKind.CONTAINER, None,
        ("postgres",), "postgres:17-alpine", "a" * 64,
        (IntegrationPortBinding("postgres", 5432, 0),),
        (IntegrationVolumeMount(
            "postgres-data", "runtime/postgres", "/var/lib/postgresql/data",
            False, 1_073_741_824,
        ),),
        IntegrationHealthCheck(
            IntegrationHealthKind.TCP, "postgres", None, None, 2, 1, 30,
        ),
        (), (),
    )
    plan = IntegrationEnvironmentPlan(
        "environment-1", "task-1", "candidate-1", "changeset-1", "host-1",
        "/candidate/workspace", (service,), IntegrationNetworkMode.ISOLATED, (),
        ("artifacts/postgres.log",),
        EngineeringResourceImpact(600, 2, 1, 4, 1_073_741_824, 1_000_000),
        536_870_912, 1000,
        (EngineeringAuthority.EXECUTE,), True, NOW, NOW + timedelta(minutes=20),
    )
    permit = IntegrationExecutionPermit(
        "environment-permit-1", plan.environment_id, plan.approved_changeset_id,
        plan.exact_host_id, ("authorization-1",), NOW,
        NOW + timedelta(minutes=5),
    )
    receipt = IntegrationEnvironmentReceipt(
        "environment-receipt-1", plan.environment_id, permit.permit_id,
        IntegrationEnvironmentStatus.READY, NOW, NOW + timedelta(seconds=5),
        (IntegrationServiceReceipt(
            service.service_id, "container-1", service.image_sha256,
            (IntegrationAllocatedPort("postgres", 49152),), "health-1", None,
        ),),
        (IntegrationRetainedArtifact("artifacts/postgres.log", "b" * 64),), (),
    )
    result = IntegrationEnvironmentStartResult(
        plan.environment_id, integration_environment_plan_digest(plan),
        permit, receipt,
    )
    return service, plan, permit, receipt, result


def integration_network_schema_values() -> tuple[object, ...]:
    _service, plan, permit, _receipt, _result = integration_environment_schema_values()
    attachment = IntegrationNetworkAttachment(
        IntegrationNetworkAttachmentKind.DOCKER_INTERNAL_NETWORK,
        "fam-integration-environment-1", "http://[fd00::1]:43121",
    )
    network_request = IntegrationNetworkEnforcementRequest(
        "network-request-1", plan.environment_id, permit.permit_id,
        plan.exact_host_id, "principal-1", "session-1", "decision-1",
        "device-1", base64.b64encode(b"x" * 64).decode("ascii"),
        integration_environment_plan_digest(plan),
        (IntegrationNetworkAttachmentKind.DOCKER_INTERNAL_NETWORK,),
        ("pypi.org:443",), plan.resource_impact.max_network_bytes,
        permit.expires_at,
    )
    network_lease = IntegrationNetworkLease(
        "network-enforcement-1", network_request.request_id,
        plan.environment_id, network_request.principal_id,
        network_request.session_id, network_request.authority_ref,
        (attachment,), network_request.destinations,
        network_request.maximum_network_bytes, NOW,
        network_request.expires_at, "c" * 64,
    )
    network_usage = IntegrationNetworkUsage(
        network_lease.enforcement_id, plan.environment_id,
        network_lease.destinations, 100, 200,
        network_lease.maximum_network_bytes, False, True,
        NOW + timedelta(seconds=5), "d" * 64,
    )
    return network_request, attachment, network_lease, network_usage
