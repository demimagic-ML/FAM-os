"""Provider-neutral sink for required application-action audit records."""

from typing import Protocol

from fam_os.applications.action_audit import (
    ApplicationActionAuditIntent, ApplicationActionAuditRecord,
    ApplicationActionAuditVerification,
)


class ApplicationActionAuditSink(Protocol):
    def append(self, intent: ApplicationActionAuditIntent) -> ApplicationActionAuditRecord: ...

    def verify(self) -> ApplicationActionAuditVerification: ...
