"""Core-owned admission gateway for local API, Shell, and MCP clients."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from jsonschema import Draft202012Validator, ValidationError

from fam_os.core.admission import (
    RequestAdmissionService, RequestAuthorityRegistry, RequestIdentity,
)
from fam_os.core.contracts import (
    FailureCategory, FailureComponent, FailureEnvelope, ResultStatus,
    RetryDisposition, TaskRequest, TaskResult,
)
from fam_os.core.ingress.contracts import CoreIngressRequest
from fam_os.core.ingress.ports import CoreTaskExecutor, IngressCapabilityRegistry


def _utc_now():
    return datetime.now(timezone.utc)


def _identifier():
    return str(uuid4())


@dataclass(slots=True)
class LifecycleCoreIngressGateway:
    capabilities: IngressCapabilityRegistry
    authorities: RequestAuthorityRegistry
    admission: RequestAdmissionService
    executor: CoreTaskExecutor
    clock: Callable[[], datetime] = _utc_now
    error_id_factory: Callable[[], str] = _identifier

    async def visible_capabilities(self, identity: RequestIdentity):
        grant = self.authorities.get(identity.authority_ref)
        if grant is None or not _identity_matches(identity, grant):
            return ()
        if not grant.active_at(self.clock()):
            return ()
        allowed = set(grant.granted_capabilities)
        return tuple(
            item for item in self.capabilities.entries()
            if item.capability_id in allowed
        )

    async def invoke(self, identity, request):
        capability = self.capabilities.get(request.capability_id)
        if capability is None:
            return self._failed(
                request.request_id, FailureCategory.INVALID_REQUEST,
                "ingress.capability_unknown", "The requested capability is unavailable.",
                RetryDisposition.NEVER, request.capability_id,
            )
        try:
            Draft202012Validator(_mutable(capability.input_schema)).validate(
                _mutable(request.parameters)
            )
        except ValidationError:
            return self._failed(
                request.request_id, FailureCategory.INVALID_REQUEST,
                "ingress.input_invalid", "The capability input is invalid.",
                RetryDisposition.NEVER, capability.capability_id,
            )
        task = TaskRequest(
            request.request_id,
            f"Invoke approved FAM capability {capability.capability_id}.",
            (capability.capability_id,), capability.verification_required,
        )
        admitted = self.admission.admit(task, identity)
        if not admitted.accepted:
            return TaskResult(
                request.request_id, ResultStatus.FAILED, None,
                reason=admitted.failure.safe_message,
                evidence_ids=admitted.failure.evidence_ids,
                failure=admitted.failure,
            )
        try:
            result = await self.executor.execute(admitted.admitted, request.parameters)
        except Exception:
            return self._failed(
                request.request_id, FailureCategory.INTERNAL,
                "ingress.execution_failed", "The request could not be completed.",
                RetryDisposition.WITH_BACKOFF, capability.capability_id,
            )
        return self._enforce_result(capability, request.request_id, result)

    def _enforce_result(self, capability, request_id, result):
        if result.request_id != request_id:
            return self._failed(
                request_id, FailureCategory.INTERNAL, "ingress.result_mismatch",
                "The request result could not be validated.",
                RetryDisposition.NEVER, capability.capability_id,
            )
        if capability.verification_required and result.status is ResultStatus.COMPLETED:
            failure = self._failure(
                FailureCategory.VERIFICATION_FAILED, "ingress.verification_required",
                "The result was withheld because verification is required.",
                RetryDisposition.NEVER, capability.capability_id,
            )
            return TaskResult(
                request_id, ResultStatus.WITHHELD, None,
                reason=failure.safe_message, failure=failure,
            )
        return result

    def _failed(self, request_id, category, code, message, retry, capability_id):
        failure = self._failure(category, code, message, retry, capability_id)
        return TaskResult(
            request_id, ResultStatus.FAILED, None,
            reason=failure.safe_message, failure=failure,
        )

    def _failure(self, category, code, message, retry, capability_id):
        return FailureEnvelope(
            self.error_id_factory(), category, code, message,
            FailureComponent.CORE, retry, capability_id=capability_id,
        )


def _identity_matches(identity, grant):
    return (
        identity.authority_ref, identity.principal_id, identity.session_id
    ) == (grant.authority_ref, grant.principal_id, grant.session_id)


def _mutable(value):
    if hasattr(value, "items"):
        return {key: _mutable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_mutable(item) for item in value]
    return value
