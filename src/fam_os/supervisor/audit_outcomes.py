"""Stable privacy-safe audit outcomes for Supervisor exceptions."""

from fam_os.supervisor.audit_contracts import SupervisorAuditOutcome
from fam_os.supervisor.errors import (
    ServiceRecoveryError,
    ServiceDefinitionConflictError,
    ServiceOwnershipError,
    SupervisorAuthorizationError,
)


def audit_failure(error: Exception) -> tuple[SupervisorAuditOutcome, str]:
    if isinstance(error, SupervisorAuthorizationError):
        return SupervisorAuditOutcome.DENIED, "authorization.denied"
    if isinstance(error, ServiceOwnershipError):
        return SupervisorAuditOutcome.DENIED, "ownership.denied"
    if isinstance(error, ServiceDefinitionConflictError):
        return SupervisorAuditOutcome.DENIED, "definition.conflict"
    if isinstance(error, ServiceRecoveryError):
        return SupervisorAuditOutcome.FAILED, "recovery.incomplete"
    return SupervisorAuditOutcome.FAILED, "operation.failed"
