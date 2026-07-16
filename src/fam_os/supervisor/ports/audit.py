"""Provider-neutral immutable Supervisor audit sink."""

from typing import Protocol

from fam_os.supervisor.audit_contracts import (
    AuditChainVerification,
    SupervisorAuditIntent,
    SupervisorAuditRecord,
)


class SupervisorAuditSink(Protocol):
    def append(self, intent: SupervisorAuditIntent) -> SupervisorAuditRecord: ...

    def verify(self) -> AuditChainVerification: ...
