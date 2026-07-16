"""Allowlisted access resources and active grant state."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

from fam_os.supervisor.access_contracts import (
    AccessResourceDescriptor,
    ServiceAccessGrant,
)
from fam_os.supervisor.errors import SupervisorAuthorizationError


@dataclass(slots=True)
class InMemoryAccessResourceCatalog:
    resources: tuple[AccessResourceDescriptor, ...]
    _by_id: dict[str, AccessResourceDescriptor] = field(init=False)

    def __post_init__(self) -> None:
        self._by_id = {item.resource_id: item for item in self.resources}
        if not self.resources or len(self._by_id) != len(self.resources):
            raise ValueError("access resource catalog must be non-empty and unique")

    def require(self, resource_id: str) -> AccessResourceDescriptor:
        resource = self._by_id.get(resource_id)
        if resource is None:
            raise SupervisorAuthorizationError("access resource is not allowlisted")
        return resource


@dataclass(frozen=True, slots=True)
class RecordedAccessGrant:
    grant: ServiceAccessGrant
    revoked_at: datetime | None = None

    @property
    def revoked(self) -> bool:
        return self.revoked_at is not None


@dataclass(slots=True)
class InMemoryAccessGrantRegistry:
    _grants: dict[str, RecordedAccessGrant] = field(default_factory=dict)

    def require_new(self, grant: ServiceAccessGrant) -> None:
        if grant.grant_id in self._grants:
            raise SupervisorAuthorizationError("access grant ID was already used")

    def record(self, grant: ServiceAccessGrant) -> RecordedAccessGrant:
        current = self._grants.get(grant.grant_id)
        if current is not None and current.grant != grant:
            raise SupervisorAuthorizationError("grant ID has different declared scope")
        if current is None:
            current = RecordedAccessGrant(grant)
            self._grants[grant.grant_id] = current
        return current

    def require_active(self, grant_id: str) -> RecordedAccessGrant:
        current = self._grants.get(grant_id)
        if current is None or current.revoked:
            raise SupervisorAuthorizationError("access grant is absent or revoked")
        return current

    def revoke(self, grant_id: str, instant: datetime) -> RecordedAccessGrant:
        current = self.require_active(grant_id)
        revoked = replace(current, revoked_at=instant)
        self._grants[grant_id] = revoked
        return revoked

    def get(self, grant_id: str) -> RecordedAccessGrant | None:
        return self._grants.get(grant_id)

    def unrevoked_for_service(
        self, service_id: str
    ) -> tuple[RecordedAccessGrant, ...]:
        matches = (
            item for item in self._grants.values()
            if item.grant.service_id == service_id and not item.revoked
        )
        return tuple(sorted(matches, key=lambda item: item.grant.grant_id))
