"""Durable expert-package installation state and audit contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.experts.compatibility_contracts import ExpertCompatibilityStatus
from fam_os.experts.registry_contracts import ExpertPackageCoordinate
from fam_os.registry.package import ArtifactDigest, PackageTrustLevel


PACKAGE_LIFECYCLE_CONTRACT_VERSION = "fam.registry.lifecycle/v1alpha1"


class PackageLifecycleAction(StrEnum):
    INSTALL = "install"
    UPDATE = "update"
    DISABLE = "disable"
    ROLLBACK = "rollback"
    REMOVE = "remove"
    CLEANUP = "cleanup"


@dataclass(frozen=True, slots=True)
class PendingArtifactRemoval:
    coordinate: ExpertPackageCoordinate
    artifact_locator: str

    def __post_init__(self) -> None:
        _require_text(self.artifact_locator, "artifact_locator")


@dataclass(frozen=True, slots=True)
class InstalledExpertPackage:
    coordinate: ExpertPackageCoordinate
    expert_id: str
    artifact_locator: str
    artifact_digest: ArtifactDigest
    manifest_digest: ArtifactDigest
    effective_trust: PackageTrustLevel
    trust_policy_id: str
    compatibility_status: ExpertCompatibilityStatus
    validation_profile_id: str
    installed_at: datetime
    enabled: bool

    def __post_init__(self) -> None:
        for name in ("expert_id", "artifact_locator", "trust_policy_id", "validation_profile_id"):
            _require_text(getattr(self, name), name)
        _require_aware(self.installed_at, "installed_at")
        if self.compatibility_status is ExpertCompatibilityStatus.INCOMPATIBLE:
            raise ValueError("an incompatible package cannot be installed")
        if self.enabled and self.compatibility_status is ExpertCompatibilityStatus.CURRENTLY_CONSTRAINED:
            raise ValueError("a currently constrained package cannot be enabled")


@dataclass(frozen=True, slots=True)
class PackageLifecycleEvent:
    event_id: str
    revision: int
    occurred_at: datetime
    action: PackageLifecycleAction
    coordinate: ExpertPackageCoordinate
    previous_active: ExpertPackageCoordinate | None
    active_after: ExpertPackageCoordinate | None
    reason_code: str

    def __post_init__(self) -> None:
        _require_text(self.event_id, "event_id")
        _require_text(self.reason_code, "reason_code")
        _require_aware(self.occurred_at, "occurred_at")
        if self.revision <= 0:
            raise ValueError("lifecycle event revision must be positive")


@dataclass(frozen=True, slots=True)
class ExpertPackageInstallationState:
    revision: int
    packages: tuple[InstalledExpertPackage, ...]
    pending_artifact_removals: tuple[PendingArtifactRemoval, ...]
    events: tuple[PackageLifecycleEvent, ...]
    contract_version: str = PACKAGE_LIFECYCLE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != PACKAGE_LIFECYCLE_CONTRACT_VERSION:
            raise ValueError("unsupported package lifecycle contract_version")
        if self.revision < 0:
            raise ValueError("installation-state revision must not be negative")
        if self.revision == 0 and (self.packages or self.pending_artifact_removals):
            raise ValueError("revision zero installation state must be empty")
        coordinates = tuple(item.coordinate for item in self.packages)
        if len(set(coordinates)) != len(coordinates):
            raise ValueError("installed package coordinates must be unique")
        enabled_experts = tuple(item.expert_id for item in self.packages if item.enabled)
        if len(set(enabled_experts)) != len(enabled_experts):
            raise ValueError("only one package version may be enabled per expert")
        pending = tuple(item.coordinate for item in self.pending_artifact_removals)
        if len(set(pending)) != len(pending):
            raise ValueError("pending artifact removals must be unique")
        if set(coordinates) & set(pending):
            raise ValueError("an installed package cannot also be pending removal")
        revisions = tuple(item.revision for item in self.events)
        if revisions != tuple(range(1, self.revision + 1)):
            raise ValueError("lifecycle events must form the complete revision history")


def empty_installation_state() -> ExpertPackageInstallationState:
    return ExpertPackageInstallationState(0, (), (), ())


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
