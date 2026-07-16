"""Start owned services only when requested cgroup limits are observed."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.supervisor.access import SupervisorCallContext
from fam_os.supervisor.boundary import SupervisorCapability
from fam_os.supervisor.contracts import ResourceSnapshot, ServiceDefinition, ServiceStatus
from fam_os.supervisor.lifecycle import OwnedServiceLifecycle
from fam_os.supervisor.limit_verification import (
    AppliedLimitsVerification,
    verify_applied_limits,
)
from fam_os.supervisor.ports import ResourceObserver


@dataclass(frozen=True, slots=True)
class ConstrainedStartOutcome:
    start_status: ServiceStatus
    snapshot: ResourceSnapshot | None
    verification: AppliedLimitsVerification
    cleanup_status: ServiceStatus | None = None

    @property
    def constrained(self) -> bool:
        return self.verification.passed and self.cleanup_status is None


@dataclass(slots=True)
class ConstrainedServiceLifecycle:
    owned: OwnedServiceLifecycle
    resources: ResourceObserver

    def start(
        self, context: SupervisorCallContext, definition: ServiceDefinition
    ) -> ConstrainedStartOutcome:
        self.owned.authorizer.require(
            context,
            SupervisorCapability.APPLY_SERVICE_RESOURCE_LIMITS,
            definition.service_id,
        )
        start_status = self.owned.start(context, definition)
        snapshot = self.resources.observe(definition.service_id)
        verification = verify_applied_limits(
            definition.limits, snapshot, definition.service_id
        )
        cleanup = None
        if not verification.passed:
            cleanup = self.owned.lifecycle.stop(definition.service_id)
        return ConstrainedStartOutcome(
            start_status, snapshot, verification, cleanup
        )
