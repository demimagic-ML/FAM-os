"""Deterministic request admission before routing or model execution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fam_os.core.admission.contracts import (
    AdmittedTaskRequest,
    RequestAdmissionOutcome,
    RequestAuthorityGrant,
    RequestIdentity,
    RequestPermissionContext,
)
from fam_os.core.admission.ports import RequestAuthorityRegistry, RequestReplayRegistry
from fam_os.core.contracts import (
    FailureCategory,
    FailureComponent,
    FailureEnvelope,
    RetryDisposition,
    TaskRequest,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier() -> str:
    return str(uuid4())


@dataclass(slots=True)
class RequestAdmissionService:
    authorities: RequestAuthorityRegistry
    replays: RequestReplayRegistry
    clock: Callable[[], datetime] = _utc_now
    admission_id_factory: Callable[[], str] = _identifier
    error_id_factory: Callable[[], str] = _identifier

    def admit(
        self, request: TaskRequest, identity: RequestIdentity
    ) -> RequestAdmissionOutcome:
        instant = self.clock()
        grant = self.authorities.get(identity.authority_ref)
        failure = self._authority_failure(request, identity, grant, instant)
        if failure is not None:
            return RequestAdmissionOutcome(request.request_id, failure=failure)
        if not self.replays.reserve(request.request_id):
            return self._reject(
                request, FailureCategory.INVALID_REQUEST,
                "admission.request_replayed", "Request ID was already admitted.",
                RetryDisposition.NEVER,
            )
        permission = RequestPermissionContext(
            identity.principal_id, identity.session_id, identity.authority_ref,
            request.required_capabilities, grant.expires_at,
        )
        admitted = AdmittedTaskRequest(
            self.admission_id_factory(), request, permission, instant
        )
        return RequestAdmissionOutcome(request.request_id, admitted=admitted)

    def _authority_failure(self, request, identity, grant, instant):
        if grant is None or not _identity_matches(identity, grant):
            return self._failure(
                FailureCategory.PERMISSION_DENIED, "admission.authority_denied",
                "Request authority is unavailable or invalid.",
                RetryDisposition.AFTER_USER_ACTION,
            )
        if not grant.active_at(instant):
            return self._failure(
                FailureCategory.PERMISSION_DENIED, "admission.authority_inactive",
                "Request authority is not active.",
                RetryDisposition.AFTER_USER_ACTION,
            )
        missing = tuple(
            capability for capability in request.required_capabilities
            if capability not in grant.granted_capabilities
        )
        if missing:
            return self._failure(
                FailureCategory.PERMISSION_DENIED, "admission.capability_denied",
                "A required capability is not authorized.",
                RetryDisposition.AFTER_USER_ACTION, missing[0],
            )
        return None

    def _reject(self, request, category, code, message, retry):
        return RequestAdmissionOutcome(
            request.request_id,
            failure=self._failure(category, code, message, retry),
        )

    def _failure(self, category, code, message, retry, capability_id=None):
        return FailureEnvelope(
            self.error_id_factory(), category, code, message,
            FailureComponent.CORE, retry, capability_id=capability_id,
        )


def _identity_matches(
    identity: RequestIdentity, grant: RequestAuthorityGrant
) -> bool:
    return (
        identity.authority_ref, identity.principal_id, identity.session_id
    ) == (grant.authority_ref, grant.principal_id, grant.session_id)
