"""Deterministic registry of FAM-owned service definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from fam_os.supervisor.contracts import ServiceDefinition
from fam_os.supervisor.errors import (
    ServiceDefinitionConflictError,
    ServiceOwnershipError,
)


@dataclass(frozen=True, slots=True)
class OwnedService:
    principal_id: str
    session_id: str
    definition: ServiceDefinition

    def __post_init__(self) -> None:
        if not self.principal_id.strip() or not self.session_id.strip():
            raise ValueError("owned service requires principal and session identity")


class ServiceOwnershipRegistry(Protocol):
    def claim(self, service: OwnedService) -> OwnedService: ...

    def require_owned(
        self, service_id: str, principal_id: str, session_id: str
    ) -> OwnedService: ...


@dataclass(slots=True)
class InMemoryServiceOwnershipRegistry:
    _services: dict[str, OwnedService] = field(default_factory=dict)

    def claim(self, service: OwnedService) -> OwnedService:
        service_id = service.definition.service_id
        _require_fam_namespace(service_id)
        current = self._services.get(service_id)
        if current is None:
            self._services[service_id] = service
            return service
        if _owner(current) != _owner(service):
            raise ServiceOwnershipError("service ID is owned by another caller")
        if current.definition != service.definition:
            raise ServiceDefinitionConflictError(
                "owned service ID has a different declared definition"
            )
        return current

    def require_owned(
        self, service_id: str, principal_id: str, session_id: str
    ) -> OwnedService:
        _require_fam_namespace(service_id)
        current = self._services.get(service_id)
        if current is None or _owner(current) != (principal_id, session_id):
            raise ServiceOwnershipError("caller does not own the requested service")
        return current

    def get(self, service_id: str) -> OwnedService | None:
        return self._services.get(service_id)


def _owner(service: OwnedService) -> tuple[str, str]:
    return service.principal_id, service.session_id


def _require_fam_namespace(service_id: str) -> None:
    if not service_id.startswith("fam-"):
        raise ServiceOwnershipError("service ID is outside the FAM-owned namespace")
