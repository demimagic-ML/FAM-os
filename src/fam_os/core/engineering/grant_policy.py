"""Deterministic admission and use of owner-authenticated engineering grants."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import PurePosixPath
from typing import Protocol
from uuid import uuid4

from fam_os.core.engineering.break_glass import (
    BreakGlassChallenge,
    BreakGlassDecision,
    BreakGlassDisposition,
)
from fam_os.core.engineering.grants import (
    EngineeringAuthorityGrant,
    EngineeringAuthorizationDecision,
    EngineeringAuthorizationRequest,
    EngineeringGrantScopeKind,
    GrantLifecycleState,
    OwnerGrantApproval,
)


class OwnerAuthorityVerifier(Protocol):
    def verify_grant(
        self, approval: OwnerGrantApproval, grant_sha256: str,
    ) -> bool: ...

    def verify_break_glass(
        self, challenge: BreakGlassChallenge, decision: BreakGlassDecision,
    ) -> bool: ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier() -> str:
    return str(uuid4())


@dataclass(slots=True)
class EngineeringGrantLedger:
    owner_verifier: OwnerAuthorityVerifier
    clock: Callable[[], datetime] = _utc_now
    identifier: Callable[[], str] = _identifier
    _grants: dict[str, EngineeringAuthorityGrant] = field(
        init=False, default_factory=dict,
    )

    def __post_init__(self) -> None:
        self._grants.clear()

    def activate(
        self,
        grant: EngineeringAuthorityGrant,
        approval: OwnerGrantApproval,
        challenge: BreakGlassChallenge | None = None,
        decision: BreakGlassDecision | None = None,
    ) -> None:
        now = self.clock()
        fingerprint = engineering_grant_digest(grant)
        if (
            grant.grant_id in self._grants
            or not grant.active_at(now)
            or approval.grant_id != grant.grant_id
            or approval.owner_id != grant.owner_id
            or approval.grant_sha256 != fingerprint
            or approval.approved_at < grant.issued_at
            or approval.approved_at >= grant.expires_at
            or not self.owner_verifier.verify_grant(approval, fingerprint)
        ):
            raise PermissionError("engineering grant lacks exact owner approval")
        if grant.requires_break_glass:
            self._require_break_glass(grant, challenge, decision, now)
        elif challenge is not None or decision is not None:
            raise PermissionError("ordinary engineering grant cannot inherit break-glass scope")
        self._grants[grant.grant_id] = grant

    def authorize(
        self, request: EngineeringAuthorizationRequest,
    ) -> EngineeringAuthorizationDecision:
        now = self.clock()
        grant = self._grants.get(request.grant_id)
        reason = self._rejection(grant, request, now)
        return EngineeringAuthorizationDecision(
            self.identifier(), request.request_id, request.grant_id,
            request.authority, now, reason is None, reason or "authorized",
        )

    def revoke(self, grant_id: str, owner_id: str) -> EngineeringAuthorityGrant:
        grant = self._grants.get(grant_id)
        if grant is None or grant.owner_id != owner_id:
            raise KeyError("owner engineering grant is unavailable")
        if grant.state is not GrantLifecycleState.ACTIVE:
            return grant
        revoked = replace(
            grant, state=GrantLifecycleState.REVOKED, revoked_at=self.clock(),
        )
        self._grants[grant_id] = revoked
        return revoked

    def consume(self, grant_id: str, effect_id: str) -> EngineeringAuthorityGrant:
        grant = self._grants.get(grant_id)
        if grant is None:
            raise KeyError("engineering grant is unavailable")
        if grant.scope.kind not in {
            EngineeringGrantScopeKind.ACTION,
            EngineeringGrantScopeKind.CHANGESET,
        }:
            return grant
        if grant.state is not GrantLifecycleState.ACTIVE:
            raise PermissionError("engineering grant is no longer active")
        if not effect_id.strip():
            raise ValueError("effect_id must be nonempty")
        consumed = replace(
            grant, state=GrantLifecycleState.CONSUMED, consumed_at=self.clock(),
        )
        self._grants[grant_id] = consumed
        return consumed

    def get(self, grant_id: str) -> EngineeringAuthorityGrant | None:
        return self._grants.get(grant_id)

    def _require_break_glass(self, grant, challenge, decision, now) -> None:
        if challenge is None or decision is None:
            raise PermissionError("exceptional engineering grant requires break-glass approval")
        if (
            grant.break_glass_decision_id != decision.decision_id
            or challenge.challenge_id != decision.challenge_id
            or grant.grant_id != challenge.grant_id
            or grant.grant_id != decision.grant_id
            or grant.owner_id != challenge.owner_id
            or grant.owner_id != decision.owner_id
            or grant.authorities != challenge.authorities
            or grant.verification is not challenge.verification
            or grant.scope.kind is not challenge.scope_kind
            or grant.scope.scope_id != challenge.scope_id
            or decision.scope_kind is not challenge.scope_kind
            or decision.scope_id != challenge.scope_id
            or decision.consequences_sha256 != challenge.consequences_sha256
            or decision.disposition is not BreakGlassDisposition.APPROVED
            or not (challenge.issued_at <= decision.decided_at < challenge.expires_at)
            or not (challenge.issued_at <= now < challenge.expires_at)
            or not self.owner_verifier.verify_break_glass(challenge, decision)
        ):
            raise PermissionError("break-glass approval does not match exact consequences")

    @staticmethod
    def _rejection(grant, request, now) -> str | None:
        if grant is None:
            return "grant_not_admitted"
        if not grant.active_at(now):
            return "grant_inactive"
        if request.principal_id != grant.principal_id:
            return "principal_mismatch"
        if request.authority not in grant.authorities:
            return "authority_missing"
        scope = grant.scope
        target = {
            EngineeringGrantScopeKind.ACTION: request.action_id,
            EngineeringGrantScopeKind.CHANGESET: request.change_set_id,
            EngineeringGrantScopeKind.TASK: request.task_id,
            EngineeringGrantScopeKind.SESSION: request.session_id,
        }[scope.kind]
        if target != scope.scope_id:
            return "target_mismatch"
        if request.workspace_root not in scope.workspace_roots:
            return "workspace_mismatch"
        if request.path is not None and not _path_allowed(
            request.path, scope.path_allowlist, scope.path_denylist,
        ):
            return "path_denied"
        constrained = (
            (request.toolchain, scope.toolchains),
            (request.network_host, scope.network_hosts),
            (request.package_registry, scope.package_registries),
            (request.git_remote, scope.git_remotes),
            (request.git_branch, scope.git_branches),
            (request.secret_ref, scope.secret_refs),
        )
        if any(value is not None and value not in allowed for value, allowed in constrained):
            return "resource_scope_mismatch"
        requested = request.resource_impact
        allowed = grant.resource_impact
        for name in (
            "max_wall_seconds", "max_tool_runs", "max_processes",
            "max_changed_files", "max_changed_bytes", "max_network_bytes",
        ):
            if getattr(requested, name) > getattr(allowed, name):
                return "resource_budget_exceeded"
        return None


def engineering_grant_digest(grant: EngineeringAuthorityGrant) -> str:
    payload = json.dumps(
        _json_value(asdict(grant)), sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _json_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _path_allowed(path: str, allowlist: tuple[str, ...], denylist: tuple[str, ...]) -> bool:
    value = PurePosixPath(path)
    if any(value.match(pattern) for pattern in denylist):
        return False
    return not allowlist or any(value.match(pattern) for pattern in allowlist)
