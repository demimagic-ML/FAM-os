"""Privacy-bounded construction and required emission of Supervisor audit intent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fam_os.supervisor.access import SupervisorCallContext
from fam_os.supervisor.audit_contracts import (
    SupervisorAuditIntent,
    SupervisorAuditOperation,
    SupervisorAuditOutcome,
    SupervisorAuditRecord,
)
from fam_os.supervisor.ports.audit import SupervisorAuditSink


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _event_id() -> str:
    return str(uuid4())


@dataclass(slots=True)
class SupervisorAuditEmitter:
    sink: SupervisorAuditSink
    clock: Callable[[], datetime] = _utc_now
    event_id_factory: Callable[[], str] = _event_id
    operation_id_factory: Callable[[], str] = _event_id

    def new_operation_id(self) -> str:
        return self.operation_id_factory()

    def emit(
        self,
        context: SupervisorCallContext,
        service_id: str,
        operation: SupervisorAuditOperation,
        outcome: SupervisorAuditOutcome,
        operation_id: str,
        *,
        resource_id: str | None = None,
        reason_code: str | None = None,
        evidence_ref: str | None = None,
    ) -> SupervisorAuditRecord:
        intent = SupervisorAuditIntent(
            self.event_id_factory(),
            operation_id,
            self.clock(),
            context.request_id,
            context.authority_ref,
            context.principal_id,
            context.session_id,
            service_id,
            operation,
            outcome,
            resource_id,
            reason_code,
            evidence_ref,
        )
        return self.sink.append(intent)
