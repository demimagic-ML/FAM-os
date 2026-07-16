"""Required-audit composition for applied resource-limit verification."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.supervisor.access import SupervisorCallContext
from fam_os.supervisor.audit import SupervisorAuditEmitter
from fam_os.supervisor.audit_contracts import (
    SupervisorAuditOperation,
    SupervisorAuditOutcome,
)
from fam_os.supervisor.audit_outcomes import audit_failure
from fam_os.supervisor.constrained import (
    ConstrainedServiceLifecycle,
    ConstrainedStartOutcome,
)
from fam_os.supervisor.contracts import ServiceDefinition
from fam_os.supervisor.errors import AuditEmissionError


@dataclass(slots=True)
class AuditedConstrainedServiceLifecycle:
    constrained: ConstrainedServiceLifecycle
    audit: SupervisorAuditEmitter

    def start(
        self, context: SupervisorCallContext, definition: ServiceDefinition
    ) -> ConstrainedStartOutcome:
        operation = SupervisorAuditOperation.APPLY_RESOURCE_LIMITS
        operation_id = self.audit.new_operation_id()
        self.audit.emit(
            context, definition.service_id, operation,
            SupervisorAuditOutcome.REQUESTED,
            operation_id,
        )
        try:
            outcome = self.constrained.start(context, definition)
        except Exception as error:
            audit_outcome, reason = audit_failure(error)
            self.audit.emit(
                context, definition.service_id, operation,
                audit_outcome, operation_id, reason_code=reason,
            )
            raise
        self._emit_outcome(context, definition, outcome, operation_id)
        return outcome

    def _emit_outcome(self, context, definition, outcome, operation_id) -> None:
        audit_outcome = (
            SupervisorAuditOutcome.SUCCEEDED
            if outcome.constrained
            else SupervisorAuditOutcome.COMPENSATED
        )
        reason = None if outcome.constrained else "limits.verification_failed"
        evidence = "limits.verified" if outcome.constrained else "service.inactive"
        try:
            self.audit.emit(
                context, definition.service_id,
                SupervisorAuditOperation.APPLY_RESOURCE_LIMITS,
                audit_outcome, operation_id,
                reason_code=reason, evidence_ref=evidence,
            )
        except Exception as error:
            self._rollback_if_running(definition.service_id, outcome, error)

    def _rollback_if_running(self, service_id, outcome, audit_error) -> None:
        if outcome.constrained:
            try:
                self.constrained.owned.lifecycle.stop(service_id)
            except Exception as cleanup_error:
                raise AuditEmissionError(
                    "audit failed after limit verification and stop failed"
                ) from cleanup_error
        raise audit_error
