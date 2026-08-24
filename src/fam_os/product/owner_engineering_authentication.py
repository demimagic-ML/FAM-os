"""Single-use local-owner contexts for exact engineering consequences."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from fam_os.core.engineering.break_glass import BreakGlassChallenge, BreakGlassDecision
from fam_os.core.engineering.grants import OwnerGrantApproval


ENGINEERING_OWNER_PURPOSES = frozenset({
    "engineering-grant", "engineering-break-glass",
    "engineering-secret-provision", "engineering-secret-rotate",
    "engineering-secret-delete",
})


@dataclass(frozen=True, slots=True)
class OwnerEngineeringAuthenticationContext:
    context_id: str
    owner_id: str
    purpose: str
    payload_sha256: str
    issued_at: datetime
    expires_at: datetime
    transport_session_id: str | None = None


class OwnerEngineeringAuthenticationRegistry:
    def __init__(
        self,
        owner_id: str,
        clock: Callable[[], datetime] | None = None,
        identifier: Callable[[], str] | None = None,
    ) -> None:
        self._owner_id = owner_id
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier = identifier or (lambda: str(uuid4()))
        self._contexts: dict[str, OwnerEngineeringAuthenticationContext] = {}
        self._lock = Lock()

    def issue(
        self, owner_id: str, purpose: str, payload_sha256: str,
        transport_session_id: str | None = None,
    ) -> OwnerEngineeringAuthenticationContext:
        if owner_id != self._owner_id or purpose not in ENGINEERING_OWNER_PURPOSES:
            raise PermissionError("owner engineering authentication scope is invalid")
        if len(payload_sha256) != 64:
            raise ValueError("owner engineering authentication digest is invalid")
        int(payload_sha256, 16)
        if transport_session_id is not None and not transport_session_id.strip():
            raise ValueError("owner engineering transport session is invalid")
        now = self._clock()
        context = OwnerEngineeringAuthenticationContext(
            self._identifier(), owner_id, purpose, payload_sha256,
            now, now + timedelta(minutes=2), transport_session_id,
        )
        with self._lock:
            self._contexts[context.context_id] = context
        return context

    def belongs_to_session(self, context_id: str, session_id: str) -> bool:
        now = self._clock()
        with self._lock:
            context = self._contexts.get(context_id)
            return bool(
                context is not None
                and context.issued_at <= now < context.expires_at
                and context.transport_session_id is not None
                and hmac.compare_digest(context.transport_session_id, session_id)
            )

    def consume(
        self, context_id: str, owner_id: str, purpose: str, payload_sha256: str,
        transport_session_id: str | None = None,
    ) -> bool:
        with self._lock:
            context = self._contexts.get(context_id)
            now = self._clock()
            valid = bool(
                context is not None
                and context.owner_id == owner_id
                and context.purpose == purpose
                and context.issued_at <= now < context.expires_at
                and hmac.compare_digest(context.payload_sha256, payload_sha256)
                and (
                    transport_session_id is None
                    or context.transport_session_id is not None
                    and hmac.compare_digest(
                        context.transport_session_id, transport_session_id,
                    )
                )
            )
            if valid:
                self._contexts.pop(context_id)
            return valid


class ProductOwnerAuthorityVerifier:
    def __init__(self, contexts: OwnerEngineeringAuthenticationRegistry) -> None:
        self._contexts = contexts

    def verify_grant(
        self, approval: OwnerGrantApproval, grant_sha256: str,
    ) -> bool:
        return self._contexts.consume(
            approval.authentication_context_id, approval.owner_id,
            "engineering-grant", grant_sha256,
        )

    def verify_break_glass(
        self, challenge: BreakGlassChallenge, decision: BreakGlassDecision,
    ) -> bool:
        payload = break_glass_authentication_digest(challenge, decision)
        return self._contexts.consume(
            decision.authentication_context_id, decision.owner_id,
            "engineering-break-glass", payload,
        )


def break_glass_authentication_digest(
    challenge: BreakGlassChallenge, decision: BreakGlassDecision,
) -> str:
    payload = "\0".join((
        challenge.challenge_id, decision.decision_id,
        challenge.consequences_sha256,
    )).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
