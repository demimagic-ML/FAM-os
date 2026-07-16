"""Capability, ownership, allowlist, and evidence checks for service access."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fam_os.supervisor.access import SupervisorAuthorizer, SupervisorCallContext
from fam_os.supervisor.access_contracts import (
    AccessApplicationEvidence,
    AccessEvidenceStatus,
    AccessResourceDescriptor,
    AccessResourceKind,
    ServiceAccessGrant,
)
from fam_os.supervisor.access_registry import (
    InMemoryAccessGrantRegistry,
    InMemoryAccessResourceCatalog,
)
from fam_os.supervisor.boundary import SupervisorCapability
from fam_os.supervisor.errors import SupervisorAuthorizationError
from fam_os.supervisor.ownership import ServiceOwnershipRegistry
from fam_os.supervisor.ports import ServiceAccessAdapter


@dataclass(slots=True)
class ServiceAccessController:
    authorizer: SupervisorAuthorizer
    ownership: ServiceOwnershipRegistry
    catalog: InMemoryAccessResourceCatalog
    grants: InMemoryAccessGrantRegistry
    adapter: ServiceAccessAdapter

    def grant(
        self,
        context: SupervisorCallContext,
        grant: ServiceAccessGrant,
        instant: datetime,
    ) -> AccessApplicationEvidence:
        resource = self._admit(context, grant, instant, require_active=True)
        self.grants.require_new(grant)
        evidence = self.adapter.grant(grant, resource)
        _require_evidence(grant, evidence, AccessEvidenceStatus.GRANTED)
        self.grants.record(grant)
        return evidence

    def revoke(
        self,
        context: SupervisorCallContext,
        grant_id: str,
        instant: datetime,
    ) -> AccessApplicationEvidence:
        recorded = self.grants.require_active(grant_id)
        grant = recorded.grant
        resource = self._admit(context, grant, instant, require_active=False)
        evidence = self.adapter.revoke(grant, resource)
        _require_evidence(grant, evidence, AccessEvidenceStatus.REVOKED)
        self.grants.revoke(grant_id, instant)
        return evidence

    def _admit(
        self,
        context: SupervisorCallContext,
        grant: ServiceAccessGrant,
        instant: datetime,
        *,
        require_active: bool,
    ) -> AccessResourceDescriptor:
        _require_scope(context, grant, instant, require_active=require_active)
        resource = self.catalog.require(grant.resource_id)
        if resource.kind is not grant.kind or grant.mode not in resource.allowed_modes:
            raise SupervisorAuthorizationError("access kind or mode is not allowlisted")
        capability = _capability(resource.kind)
        self.authorizer.require(context, capability, grant.service_id)
        self.ownership.require_owned(
            grant.service_id, context.principal_id, context.session_id
        )
        return resource


def _require_scope(
    context: SupervisorCallContext,
    grant: ServiceAccessGrant,
    instant: datetime,
    *,
    require_active: bool,
) -> None:
    expected = (context.principal_id, context.session_id, context.authority_ref)
    actual = (grant.principal_id, grant.session_id, grant.authority_ref)
    expired = require_active and not grant.active_at(instant)
    if expected != actual or expired:
        raise SupervisorAuthorizationError("access grant scope is invalid or expired")


def _capability(kind: AccessResourceKind) -> SupervisorCapability:
    if kind is AccessResourceKind.DEVICE:
        return SupervisorCapability.GRANT_DECLARED_DEVICE_ACCESS
    return SupervisorCapability.GRANT_DECLARED_FILESYSTEM_ACCESS


def _require_evidence(
    grant: ServiceAccessGrant,
    evidence: AccessApplicationEvidence,
    status: AccessEvidenceStatus,
) -> None:
    expected = (grant.grant_id, grant.service_id, grant.resource_id, status)
    actual = (
        evidence.grant_id,
        evidence.service_id,
        evidence.resource_id,
        evidence.status,
    )
    if actual != expected:
        raise SupervisorAuthorizationError("access adapter returned mismatched evidence")
