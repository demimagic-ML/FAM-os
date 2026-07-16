"""Audited deterministic recovery and safe termination of owned services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from fam_os.supervisor.access import SupervisorCallContext
from fam_os.supervisor.audit import SupervisorAuditEmitter
from fam_os.supervisor.audit_contracts import (
    SupervisorAuditOperation,
    SupervisorAuditOutcome,
)
from fam_os.supervisor.audit_outcomes import audit_failure
from fam_os.supervisor.audited_access import AuditedServiceAccessController
from fam_os.supervisor.audited_lifecycle import AuditedOwnedServiceLifecycle
from fam_os.supervisor.boundary import SupervisorCapability
from fam_os.supervisor.contracts import ResourceSnapshot, ServiceState, ServiceStatus
from fam_os.supervisor.errors import ServiceRecoveryError
from fam_os.supervisor.ports.resources import ResourceObserver
from fam_os.supervisor.ports.recovery import ServiceFailureReset
from fam_os.supervisor.recovery_contracts import (
    ServiceTerminationDisposition,
    ServiceTerminationReason,
    ServiceTerminationReport,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class _TerminationState:
    initial: ServiceStatus
    final: ServiceStatus
    revoked_grant_ids: tuple[str, ...]
    resource_before: ResourceSnapshot | None


@dataclass(slots=True)
class ServiceRecoveryController:
    lifecycle: AuditedOwnedServiceLifecycle
    access: AuditedServiceAccessController
    observer: ResourceObserver
    resetter: ServiceFailureReset
    audit: SupervisorAuditEmitter
    clock: Callable[[], datetime] = _utc_now

    def terminate(
        self, context: SupervisorCallContext, service_id: str,
        reason: ServiceTerminationReason,
    ) -> ServiceTerminationReport:
        return self._execute(
            context, service_id, reason,
            SupervisorAuditOperation.TERMINATE_SERVICE, False,
        )

    def recover_failed(
        self, context: SupervisorCallContext, service_id: str
    ) -> ServiceTerminationReport:
        return self._execute(
            context, service_id, ServiceTerminationReason.SERVICE_FAILED,
            SupervisorAuditOperation.RECOVER_SERVICE, True,
        )

    def _execute(
        self, context, service_id, reason, operation, require_failed
    ) -> ServiceTerminationReport:
        operation_id = self.audit.new_operation_id()
        self.audit.emit(
            context, service_id, operation, SupervisorAuditOutcome.REQUESTED,
            operation_id, reason_code=reason.value,
        )
        try:
            state = self._terminate_state(
                context, service_id, operation, require_failed
            )
            report = _report(service_id, reason, operation, state)
        except Exception as error:
            outcome, reason_code = audit_failure(error)
            self.audit.emit(
                context, service_id, operation, outcome, operation_id,
                reason_code=reason_code,
            )
            raise
        self.audit.emit(
            context, service_id, operation, SupervisorAuditOutcome.SUCCEEDED,
            operation_id, evidence_ref=_evidence(operation),
        )
        return report

    def _terminate_state(
        self, context, service_id, operation, require_failed
    ) -> _TerminationState:
        initial = self._admit(context, service_id, operation)
        if require_failed and initial.state is not ServiceState.FAILED:
            raise ServiceRecoveryError("recovery requires a failed service")
        if initial.state is ServiceState.UNKNOWN:
            raise ServiceRecoveryError("unknown service state is not terminal evidence")
        resource_before = self._observe(service_id)
        final = self._stop_and_verify(context, service_id, initial)
        revoked = self._revoke_grants(context, service_id)
        return _TerminationState(initial, final, revoked, resource_before)

    def _admit(self, context, service_id, operation) -> ServiceStatus:
        capability = (
            SupervisorCapability.RECOVER_FAILED_SERVICE
            if operation is SupervisorAuditOperation.RECOVER_SERVICE
            else SupervisorCapability.SAFE_TERMINATE_OWNED_SERVICE
        )
        owned = self.lifecycle.owned
        owned.authorizer.require(context, capability, service_id)
        owned.registry.require_owned(
            service_id, context.principal_id, context.session_id
        )
        return owned.lifecycle.status(service_id)

    def _stop_and_verify(self, context, service_id, initial) -> ServiceStatus:
        if initial.state is ServiceState.INACTIVE:
            final = initial
        else:
            self.lifecycle.owned.stop(context, service_id)
            if initial.state is ServiceState.FAILED:
                self.resetter.reset_failed(service_id)
            final = self.lifecycle.owned.lifecycle.status(service_id)
        if final.state is not ServiceState.INACTIVE or final.main_pid is not None:
            raise ServiceRecoveryError("service did not reach verified inactive state")
        return final

    def _revoke_grants(self, context, service_id) -> tuple[str, ...]:
        instant = self.clock()
        recorded = self.access.controller.grants.unrevoked_for_service(service_id)
        grant_ids = tuple(item.grant.grant_id for item in recorded)
        for grant_id in grant_ids:
            self.access.revoke(context, service_id, grant_id, instant)
        return grant_ids

    def _observe(self, service_id: str) -> ResourceSnapshot | None:
        observed = self.observer.observe(service_id)
        if observed is not None and observed.service_id != service_id:
            raise ServiceRecoveryError("resource evidence has mismatched service")
        return observed


def _report(service_id, reason, operation, state) -> ServiceTerminationReport:
    if state.initial.state is ServiceState.INACTIVE:
        disposition = ServiceTerminationDisposition.ALREADY_INACTIVE
    elif operation is SupervisorAuditOperation.RECOVER_SERVICE:
        disposition = ServiceTerminationDisposition.RECOVERED_TO_INACTIVE
    else:
        disposition = ServiceTerminationDisposition.TERMINATED
    return ServiceTerminationReport(
        service_id, reason, disposition, state.initial, state.final,
        state.revoked_grant_ids, state.resource_before,
    )


def _evidence(operation: SupervisorAuditOperation) -> str:
    if operation is SupervisorAuditOperation.RECOVER_SERVICE:
        return "recovery.inactive"
    return "termination.inactive"
