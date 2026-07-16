"""Provider-neutral safe termination and failed-service recovery evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fam_os.supervisor.contracts import ResourceSnapshot, ServiceState, ServiceStatus


class ServiceTerminationReason(StrEnum):
    USER_REQUESTED = "termination.user_requested"
    SERVICE_FAILED = "recovery.service_failed"
    RESOURCE_BREACH = "termination.resource_breach"
    ACCESS_REVOKED = "termination.access_revoked"
    SUPERVISOR_SHUTDOWN = "termination.supervisor_shutdown"


class ServiceTerminationDisposition(StrEnum):
    ALREADY_INACTIVE = "already_inactive"
    TERMINATED = "terminated"
    RECOVERED_TO_INACTIVE = "recovered_to_inactive"


@dataclass(frozen=True, slots=True)
class ServiceTerminationReport:
    service_id: str
    reason: ServiceTerminationReason
    disposition: ServiceTerminationDisposition
    initial_status: ServiceStatus
    final_status: ServiceStatus
    revoked_grant_ids: tuple[str, ...]
    resource_before: ResourceSnapshot | None = None

    def __post_init__(self) -> None:
        if not self.service_id.startswith("fam-"):
            raise ValueError("termination report service is outside FAM namespace")
        if self.initial_status.service_id != self.service_id:
            raise ValueError("initial status does not match terminated service")
        if self.final_status.service_id != self.service_id:
            raise ValueError("final status does not match terminated service")
        if self.final_status.state is not ServiceState.INACTIVE:
            raise ValueError("successful termination requires inactive final state")
        if self.final_status.main_pid is not None:
            raise ValueError("inactive termination evidence cannot retain a main PID")
        if self.resource_before is not None:
            if self.resource_before.service_id != self.service_id:
                raise ValueError("resource evidence does not match terminated service")
        if tuple(sorted(set(self.revoked_grant_ids))) != self.revoked_grant_ids:
            raise ValueError("revoked grant IDs must be sorted and unique")
        self._require_disposition()

    def _require_disposition(self) -> None:
        if self.disposition is ServiceTerminationDisposition.ALREADY_INACTIVE:
            if self.initial_status.state is not ServiceState.INACTIVE:
                raise ValueError("already-inactive disposition requires inactive input")
        if self.disposition is ServiceTerminationDisposition.RECOVERED_TO_INACTIVE:
            if self.initial_status.state is not ServiceState.FAILED:
                raise ValueError("recovery disposition requires failed input")
