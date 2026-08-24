"""Owner-verified live policy over encrypted persistent engineering grants."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4
from threading import RLock

from fam_os.core.engineering.break_glass import BreakGlassChallenge, BreakGlassDecision
from fam_os.core.engineering.grant_policy import (
    EngineeringGrantLedger,
    OwnerAuthorityVerifier,
)
from fam_os.core.engineering.grants import (
    EngineeringAuthorityGrant,
    EngineeringAuthorizationDecision,
    EngineeringAuthorizationRequest,
    OwnerGrantApproval,
)
from fam_os.product.storage.engineering_grant_repository import (
    SqliteEngineeringGrantRepository,
)


class PersistentEngineeringAuthorizer:
    def __init__(
        self,
        repository: SqliteEngineeringGrantRepository,
        verifier: OwnerAuthorityVerifier,
        clock: Callable[[], datetime] | None = None,
        identifier: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier = identifier or (lambda: str(uuid4()))
        self._ledger = EngineeringGrantLedger(
            verifier, self._clock, self._identifier,
        )
        self._lock = RLock()

    def activate(
        self,
        grant: EngineeringAuthorityGrant,
        approval: OwnerGrantApproval,
        challenge: BreakGlassChallenge | None = None,
        decision: BreakGlassDecision | None = None,
    ) -> None:
        with self._lock:
            self._ledger.activate(grant, approval, challenge, decision)
            try:
                self._repository.put(grant, approval)
                if not self._repository.mark_reconfirmed(grant.grant_id):
                    raise RuntimeError("engineering grant reconfirmation was not persisted")
            except BaseException:
                self._ledger.revoke(grant.grant_id, grant.owner_id)
                raise

    def authorize(
        self, request: EngineeringAuthorizationRequest,
    ) -> EngineeringAuthorizationDecision:
        with self._lock:
            if self._repository.usable(request.grant_id) is None:
                decision = EngineeringAuthorizationDecision(
                    self._identifier(), request.request_id, request.grant_id,
                    request.authority, self._clock(), False,
                    "persistent_grant_unavailable_or_reconfirmation_required",
                )
            else:
                decision = self._ledger.authorize(request)
            self._repository.record_decision(decision)
            return decision

    def revoke(self, grant_id: str, owner_id: str) -> EngineeringAuthorityGrant:
        with self._lock:
            grant = self._ledger.revoke(grant_id, owner_id)
            stored = self._repository.get(grant_id)
            if stored is None:
                raise RuntimeError("revoked engineering grant is absent from storage")
            self._repository.put(grant, stored[1])
            return grant

    def consume(self, grant_id: str, effect_id: str) -> EngineeringAuthorityGrant:
        with self._lock:
            grant = self._ledger.consume(grant_id, effect_id)
            stored = self._repository.get(grant_id)
            if stored is None:
                raise RuntimeError("consumed engineering grant is absent from storage")
            self._repository.put(grant, stored[1])
            return grant
