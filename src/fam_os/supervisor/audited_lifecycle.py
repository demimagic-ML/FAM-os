"""Required-audit composition for owned service lifecycle operations."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.supervisor.access import SupervisorCallContext
from fam_os.supervisor.audit import SupervisorAuditEmitter
from fam_os.supervisor.audit_contracts import (
    SupervisorAuditOperation,
    SupervisorAuditOutcome,
)
from fam_os.supervisor.audit_outcomes import audit_failure
from fam_os.supervisor.contracts import (
    ServiceDefinition,
    ServiceState,
    ServiceStatus,
)
from fam_os.supervisor.errors import AuditEmissionError
from fam_os.supervisor.lifecycle import OwnedServiceLifecycle
from fam_os.supervisor.ownership import OwnedService


@dataclass(slots=True)
class AuditedOwnedServiceLifecycle:
    owned: OwnedServiceLifecycle
    audit: SupervisorAuditEmitter

    @property
    def authorizer(self):
        return self.owned.authorizer

    @property
    def lifecycle(self):
        return self.owned.lifecycle

    def declare(
        self, context: SupervisorCallContext, definition: ServiceDefinition
    ) -> OwnedService:
        operation = SupervisorAuditOperation.SERVICE_DECLARE
        operation_id = self.audit.new_operation_id()
        self._requested(context, definition.service_id, operation, operation_id)
        try:
            declared = self.owned.declare(context, definition)
        except Exception as error:
            self._failed(context, definition.service_id, operation, operation_id, error)
            raise
        self._succeeded(
            context, definition.service_id, operation, operation_id, "service.declared"
        )
        return declared

    def start(
        self, context: SupervisorCallContext, definition: ServiceDefinition
    ) -> ServiceStatus:
        operation = SupervisorAuditOperation.SERVICE_START
        operation_id = self.audit.new_operation_id()
        self._requested(context, definition.service_id, operation, operation_id)
        try:
            self.owned.declare(context, definition)
            before = self.owned.lifecycle.status(definition.service_id)
            status = self.owned.start(context, definition)
        except Exception as error:
            self._failed(context, definition.service_id, operation, operation_id, error)
            raise
        try:
            self._succeeded(
                context, definition.service_id, operation, operation_id, _evidence(status)
            )
        except Exception as error:
            self._rollback_new_start(before, status, definition.service_id, error)
        return status

    def stop(
        self, context: SupervisorCallContext, service_id: str
    ) -> ServiceStatus:
        return self._status_operation(
            context, service_id, SupervisorAuditOperation.SERVICE_STOP,
            lambda: self.owned.stop(context, service_id),
        )

    def status(
        self, context: SupervisorCallContext, service_id: str
    ) -> ServiceStatus:
        return self._status_operation(
            context, service_id, SupervisorAuditOperation.SERVICE_STATUS,
            lambda: self.owned.status(context, service_id),
        )

    def _status_operation(self, context, service_id, operation, invoke) -> ServiceStatus:
        operation_id = self.audit.new_operation_id()
        self._requested(context, service_id, operation, operation_id)
        try:
            status = invoke()
        except Exception as error:
            self._failed(context, service_id, operation, operation_id, error)
            raise
        self._succeeded(context, service_id, operation, operation_id, _evidence(status))
        return status

    def _requested(self, context, service_id, operation, operation_id) -> None:
        self.audit.emit(
            context, service_id, operation, SupervisorAuditOutcome.REQUESTED,
            operation_id,
        )

    def _succeeded(
        self, context, service_id, operation, operation_id, evidence_ref
    ) -> None:
        self.audit.emit(
            context, service_id, operation, SupervisorAuditOutcome.SUCCEEDED,
            operation_id,
            evidence_ref=evidence_ref,
        )

    def _failed(self, context, service_id, operation, operation_id, error) -> None:
        outcome, reason = audit_failure(error)
        self.audit.emit(
            context, service_id, operation, outcome, operation_id,
            reason_code=reason,
        )

    def _rollback_new_start(self, before, after, service_id, audit_error) -> None:
        newly_running = before.state not in _RUNNING and after.state in _RUNNING
        if newly_running:
            try:
                self.owned.lifecycle.stop(service_id)
            except Exception as cleanup_error:
                raise AuditEmissionError(
                    "audit failed after start and compensating stop failed"
                ) from cleanup_error
        raise audit_error


_RUNNING = frozenset((ServiceState.ACTIVE, ServiceState.ACTIVATING))


def _evidence(status: ServiceStatus) -> str:
    return f"service.{status.state.value}"
