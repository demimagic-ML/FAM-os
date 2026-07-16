"""Immutable local Expert Fabric registry state and event contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fam_os.experts.manifest import ExpertManifest


@dataclass(frozen=True, order=True, slots=True)
class ExpertPackageCoordinate:
    package_id: str
    package_version: str

    def __post_init__(self) -> None:
        if not self.package_id.strip() or not self.package_version.strip():
            raise ValueError("expert package coordinate values must not be empty")


@dataclass(frozen=True, slots=True)
class ExpertRegistrySnapshot:
    revision: int
    manifests: tuple[ExpertManifest, ...]

    def __post_init__(self) -> None:
        if self.revision < 0:
            raise ValueError("expert registry revision must not be negative")


@dataclass(frozen=True, slots=True)
class ExpertRegistryEvent:
    event_id: str
    revision: int
    occurred_at: datetime
    added: tuple[ExpertPackageCoordinate, ...]
    removed: tuple[ExpertPackageCoordinate, ...]

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("expert registry event_id must not be empty")
        if self.revision <= 0:
            raise ValueError("expert registry event revision must be positive")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("expert registry event time must be timezone-aware")
        if not self.added and not self.removed:
            raise ValueError("expert registry event must describe a change")
        if len(set(self.added)) != len(self.added) or len(set(self.removed)) != len(self.removed):
            raise ValueError("expert registry event coordinates must be unique")
        if set(self.added) & set(self.removed):
            raise ValueError("one coordinate cannot be both added and removed")


def coordinate_for(manifest: ExpertManifest) -> ExpertPackageCoordinate:
    package = manifest.package
    return ExpertPackageCoordinate(package.package_id, package.package_version)
