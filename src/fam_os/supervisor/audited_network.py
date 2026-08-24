"""Mandatory immutable audit around privileged network enforcement."""

from dataclasses import dataclass

from fam_os.supervisor.audit import SupervisorAuditEmitter
from fam_os.supervisor.audit_contracts import (
    SupervisorAuditOperation, SupervisorAuditOutcome,
)
from fam_os.supervisor.audit_outcomes import audit_failure
from fam_os.supervisor.errors import AuditEmissionError
from fam_os.supervisor.network_control import NetworkEnforcementController


@dataclass(slots=True)
class AuditedNetworkEnforcementController:
    controller: NetworkEnforcementController
    audit: SupervisorAuditEmitter

    def open(self, context, spec, instant):
        operation = SupervisorAuditOperation.NETWORK_OPEN
        operation_id = self._requested(context, spec.enforcement_id, operation)
        try:
            lease = self.controller.open(context, spec, instant)
        except Exception as error:
            self._failure(context, spec.enforcement_id, operation, operation_id, error)
            raise
        try:
            self._success(context, spec.enforcement_id, operation, operation_id, "network.opened")
        except Exception as audit_error:
            try:
                self.controller.close(context, spec.enforcement_id)
            except Exception as cleanup_error:
                raise AuditEmissionError(
                    "network open audit and compensation both failed"
                ) from cleanup_error
            raise audit_error
        return lease

    def observe(self, context, enforcement_id):
        return self._operation(
            context, enforcement_id, SupervisorAuditOperation.NETWORK_OBSERVE,
            "network.observed", lambda: self.controller.observe(context, enforcement_id),
        )

    def close(self, context, enforcement_id):
        return self._operation(
            context, enforcement_id, SupervisorAuditOperation.NETWORK_CLOSE,
            "network.closed", lambda: self.controller.close(context, enforcement_id),
        )

    def recover(self, context, spec):
        return self._operation(
            context, spec.enforcement_id, SupervisorAuditOperation.NETWORK_RECOVER,
            "network.recovered", lambda: self.controller.recover(context, spec),
        )

    def _operation(self, context, service_id, operation, evidence, effect):
        operation_id = self._requested(context, service_id, operation)
        try:
            result = effect()
        except Exception as error:
            self._failure(context, service_id, operation, operation_id, error)
            raise
        self._success(context, service_id, operation, operation_id, evidence)
        return result

    def _requested(self, context, service_id, operation):
        operation_id = self.audit.new_operation_id()
        self.audit.emit(
            context, service_id, operation, SupervisorAuditOutcome.REQUESTED,
            operation_id,
        )
        return operation_id

    def _success(self, context, service_id, operation, operation_id, evidence):
        self.audit.emit(
            context, service_id, operation, SupervisorAuditOutcome.SUCCEEDED,
            operation_id, evidence_ref=evidence,
        )

    def _failure(self, context, service_id, operation, operation_id, error):
        outcome, reason = audit_failure(error)
        self.audit.emit(
            context, service_id, operation, outcome, operation_id,
            reason_code=reason,
        )
