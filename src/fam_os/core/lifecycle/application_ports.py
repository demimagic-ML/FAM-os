"""Fake-friendly Application Fabric ports used by Core lifecycle policy."""

from typing import Protocol

from fam_os.applications import (
    ActionPreparationRequest,
    ActionProposal,
    CapabilityRegistryEntry,
    ObservationRequest,
    ObservationResult,
    PermissionGrant,
)


class ApplicationEvidenceProvider(Protocol):
    def capability(
        self, instance_id: str, capability_id: str
    ) -> CapabilityRegistryEntry | None: ...

    def observe(self, request: ObservationRequest) -> ObservationResult: ...

    def prepare_action(self, request: ActionPreparationRequest) -> ActionProposal: ...


class ApplicationPermissionRegistry(Protocol):
    def get(self, grant_id: str) -> PermissionGrant | None: ...
