"""In-memory exact Supervisor grants derived from verified signed requests."""

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock

from fam_os.supervisor import SupervisorCapability, SupervisorAuthorizationError


@dataclass(frozen=True, slots=True)
class _VerifiedNetworkGrant:
    request_id: str
    principal_id: str
    session_id: str
    authority_ref: str
    enforcement_id: str
    expires_at: datetime


class VerifiedNetworkSupervisorAuthorizer:
    def __init__(self, clock=None):
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._grants, self._lock = {}, RLock()

    def admit(self, request, enforcement_id):
        grant = _VerifiedNetworkGrant(
            request.request_id, request.principal_id, request.session_id,
            request.authority_ref, enforcement_id, request.expires_at,
        )
        with self._lock:
            current = self._grants.get(enforcement_id)
            if current is not None and current != grant:
                raise SupervisorAuthorizationError(
                    "network enforcement authority conflicts with active grant"
                )
            if not self._clock() < grant.expires_at:
                raise SupervisorAuthorizationError("network enforcement authority is expired")
            self._grants[enforcement_id] = grant

    def require(self, context, capability, service_id):
        if capability is not SupervisorCapability.ENFORCE_ALLOWLISTED_NETWORK:
            raise SupervisorAuthorizationError("network authorizer capability is invalid")
        with self._lock:
            grant = self._grants.get(service_id)
            if grant is None or not self._clock() < grant.expires_at:
                raise SupervisorAuthorizationError("network enforcement authority is inactive")
            expected = (
                grant.request_id, grant.principal_id,
                grant.session_id, grant.authority_ref,
            )
            actual = (
                context.request_id, context.principal_id,
                context.session_id, context.authority_ref,
            )
            if actual != expected:
                raise SupervisorAuthorizationError("network enforcement authority is mismatched")

    def retire(self, enforcement_id):
        with self._lock:
            self._grants.pop(enforcement_id, None)
