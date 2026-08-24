"""Exact runtime and authority admission for PostgreSQL verification."""

from pathlib import Path

from fam_os.adapters.integration.natural_template_identity import (
    POSTGRESQL_IMAGE_REF,
    POSTGRESQL_IMAGE_SHA256,
)
from fam_os.core.engineering import (
    IntegrationEnvironmentStatus,
    IntegrationNetworkMode,
)


def admit_postgresql_runtime(
    client, plan, root, environment, receipt, permit, control, now,
):
    services = tuple(
        item for item in environment.services if item.service_id == plan.service_id
    )
    service_receipts = tuple(
        item for item in receipt.services if item.service_id == plan.service_id
    )
    if (
        len(services) != 1
        or len(service_receipts) != 1
        or services[0].image_ref != POSTGRESQL_IMAGE_REF
        or services[0].image_sha256 != POSTGRESQL_IMAGE_SHA256
        or services[0].secret_refs != (plan.connection_secret_ref,)
        or service_receipts[0].image_sha256 != POSTGRESQL_IMAGE_SHA256
        or service_receipts[0].allocated_ports
    ):
        raise PermissionError("PostgreSQL runtime is not the fixed service template")
    if (
        root != Path(environment.candidate_root)
        or root != Path(root).resolve()
        or root.is_symlink()
        or not root.is_dir()
        or environment.environment_id != plan.environment_id
        or environment.task_id != plan.task_id
        or environment.candidate_id != plan.candidate_id
        or environment.approved_changeset_id != plan.approved_changeset_id
        or environment.exact_host_id != plan.exact_host_id
        or environment.network_mode is not IntegrationNetworkMode.ISOLATED
        or environment.network_hosts
        or receipt.environment_id != plan.environment_id
        or receipt.permit_id != permit.permit_id
        or receipt.status is not IntegrationEnvironmentStatus.READY
        or permit.environment_id != plan.environment_id
        or permit.approved_changeset_id != plan.approved_changeset_id
        or permit.exact_host_id != plan.exact_host_id
        or permit.network_request is not None
        or permit.network_lease is not None
        or not permit.issued_at <= now < min(permit.expires_at, plan.expires_at)
        or control.cancelled()
        or not control.authorization_active()
    ):
        raise PermissionError("PostgreSQL verification authority is not exact")
    runtime = service_receipts[0]
    result = client.run((
        "inspect",
        "--format",
        '{{.Image}}|{{index .Config.Labels "fam.environment"}}|'
        '{{index .Config.Labels "fam.service"}}',
        runtime.runtime_id,
    ))
    expected = (
        f"sha256:{POSTGRESQL_IMAGE_SHA256}|{plan.environment_id}|{plan.service_id}"
    ).encode()
    if result.exit_code != 0 or result.output.strip() != expected:
        raise PermissionError("PostgreSQL runtime identity or labels changed")
    return runtime


class PermitBoundPostgreSQLControl:
    def __init__(self, control, permit, plan, clock) -> None:
        self._control = control
        self._permit = permit
        self._plan = plan
        self._clock = clock

    def cancelled(self) -> bool:
        return self._control.cancelled()

    def authorization_active(self) -> bool:
        now = self._clock()
        return (
            self._control.authorization_active()
            and self._permit.issued_at <= now < self._permit.expires_at
            and now < self._plan.expires_at
        )
