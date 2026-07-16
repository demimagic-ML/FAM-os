"""Required-audit composition for service filesystem and device grants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fam_os.supervisor.access import SupervisorCallContext
from fam_os.supervisor.access_contracts import (
    AccessApplicationEvidence,
    AccessResourceKind,
    ServiceAccessGrant,
)
from fam_os.supervisor.access_control import ServiceAccessController
from fam_os.supervisor.audit import SupervisorAuditEmitter
from fam_os.supervisor.audit_contracts import (
    SupervisorAuditOperation,
    SupervisorAuditOutcome,
)
from fam_os.supervisor.audit_outcomes import audit_failure
from fam_os.supervisor.errors import AuditEmissionError, SupervisorAuthorizationError


@dataclass(slots=True)
class AuditedServiceAccessController:
    controller: ServiceAccessController
    audit: SupervisorAuditEmitter

    def grant(
        self, context: SupervisorCallContext, grant: ServiceAccessGrant,
        instant: datetime,
    ) -> AccessApplicationEvidence:
        operation = _grant_operation(grant.kind)
        operation_id = self.audit.new_operation_id()
        self._emit(
            context, grant, operation, SupervisorAuditOutcome.REQUESTED, operation_id
        )
        try:
            evidence = self.controller.grant(context, grant, instant)
        except Exception as error:
            self._failure(context, grant, operation, operation_id, error)
            raise
        try:
            self._emit(
                context, grant, operation, SupervisorAuditOutcome.SUCCEEDED,
                operation_id,
                evidence_ref="access.granted",
            )
        except Exception as error:
            self._rollback_grant(context, grant, instant, error)
        return evidence

    def revoke(
        self, context: SupervisorCallContext, service_id: str,
        grant_id: str, instant: datetime,
    ) -> AccessApplicationEvidence:
        operation = SupervisorAuditOperation.REVOKE_ACCESS
        operation_id = self.audit.new_operation_id()
        current = self.controller.grants.get(grant_id)
        resource_id = None
        if current is not None and current.grant.service_id == service_id:
            resource_id = current.grant.resource_id
        self.audit.emit(
            context, service_id, operation, SupervisorAuditOutcome.REQUESTED,
            operation_id,
            resource_id=resource_id,
        )
        try:
            recorded = self.controller.grants.require_active(grant_id)
            grant = recorded.grant
            if grant.service_id != service_id:
                raise SupervisorAuthorizationError(
                    "revoke service scope does not match grant"
                )
            evidence = self.controller.revoke(context, grant_id, instant)
        except Exception as error:
            outcome, reason = audit_failure(error)
            self.audit.emit(
                context, service_id, operation, outcome, operation_id,
                reason_code=reason,
            )
            raise
        self._emit(
            context, grant, operation, SupervisorAuditOutcome.SUCCEEDED,
            operation_id,
            evidence_ref="access.revoked",
        )
        return evidence

    def _failure(self, context, grant, operation, operation_id, error) -> None:
        outcome, reason = audit_failure(error)
        self._emit(
            context, grant, operation, outcome, operation_id, reason_code=reason
        )

    def _emit(
        self, context, grant, operation, outcome, operation_id, **references
    ) -> None:
        self.audit.emit(
            context, grant.service_id, operation, outcome,
            operation_id,
            resource_id=grant.resource_id, **references,
        )

    def _rollback_grant(self, context, grant, instant, audit_error) -> None:
        try:
            self.controller.revoke(context, grant.grant_id, instant)
        except Exception as cleanup_error:
            raise AuditEmissionError(
                "audit failed after access grant and revocation failed"
            ) from cleanup_error
        raise audit_error


def _grant_operation(kind: AccessResourceKind) -> SupervisorAuditOperation:
    if kind is AccessResourceKind.DEVICE:
        return SupervisorAuditOperation.GRANT_DEVICE_ACCESS
    return SupervisorAuditOperation.GRANT_FILESYSTEM_ACCESS
