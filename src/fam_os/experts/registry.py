"""Atomic local index of discovered expert package manifests."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from fam_os.experts.capabilities import parse_expert_capability_id
from fam_os.experts.contracts import ExpertTier
from fam_os.experts.manifest import ExpertManifest
from fam_os.experts.ports import ExpertManifestSource
from fam_os.experts.registry_contracts import (
    ExpertPackageCoordinate,
    ExpertRegistryEvent,
    ExpertRegistrySnapshot,
    coordinate_for,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _event_id() -> str:
    return str(uuid4())


def _manifest_key(manifest: ExpertManifest) -> tuple[str, str, str]:
    package = manifest.package
    return manifest.expert_id, package.package_id, package.package_version


@dataclass(slots=True)
class LocalExpertRegistry:
    """Thread-safe replaceable catalog; installation state remains separate."""

    clock: Callable[[], datetime] = _utc_now
    event_id_factory: Callable[[], str] = _event_id
    _by_coordinate: dict[ExpertPackageCoordinate, ExpertManifest] = field(default_factory=dict)
    _by_expert: dict[str, tuple[ExpertManifest, ...]] = field(default_factory=dict)
    _by_capability: dict[str, tuple[ExpertManifest, ...]] = field(default_factory=dict)
    _by_publisher: dict[str, tuple[ExpertManifest, ...]] = field(default_factory=dict)
    _events: list[ExpertRegistryEvent] = field(default_factory=list)
    _revision: int = 0
    _lock: Lock = field(default_factory=Lock)

    def refresh(self, manifests: Iterable[ExpertManifest]) -> bool:
        updated = _validated_catalog(manifests)
        with self._lock:
            if updated == self._by_coordinate:
                return False
            old_coordinates = set(self._by_coordinate)
            new_coordinates = set(updated)
            added = tuple(sorted(new_coordinates - old_coordinates))
            removed = tuple(sorted(old_coordinates - new_coordinates))
            changed = tuple(
                sorted(
                    key
                    for key in old_coordinates & new_coordinates
                    if updated[key] != self._by_coordinate[key]
                )
            )
            if changed:
                raise ValueError("expert package coordinate content changed without a new version")
            event = ExpertRegistryEvent(
                self.event_id_factory(), self._revision + 1, self.clock(), added, removed
            )
            self._commit(updated, event)
            return True

    def refresh_from(self, source: ExpertManifestSource) -> bool:
        return self.refresh(source.load())

    def lookup(self, package_id: str, package_version: str) -> ExpertManifest | None:
        coordinate = ExpertPackageCoordinate(package_id, package_version)
        with self._lock:
            return self._by_coordinate.get(coordinate)

    def versions(self, expert_id: str) -> tuple[ExpertManifest, ...]:
        _require_text(expert_id, "expert_id")
        with self._lock:
            return self._by_expert.get(expert_id, ())

    def find_by_capability(
        self,
        capability_id: str,
        tier: ExpertTier | None = None,
    ) -> tuple[ExpertManifest, ...]:
        capability = parse_expert_capability_id(capability_id).value
        if tier is not None and not isinstance(tier, ExpertTier):
            raise ValueError("tier must be an ExpertTier")
        with self._lock:
            values = self._by_capability.get(capability, ())
        return values if tier is None else tuple(item for item in values if item.tier is tier)

    def find_by_publisher(self, publisher_id: str) -> tuple[ExpertManifest, ...]:
        _require_text(publisher_id, "publisher_id")
        with self._lock:
            return self._by_publisher.get(publisher_id, ())

    def snapshot(self) -> ExpertRegistrySnapshot:
        with self._lock:
            values = tuple(sorted(self._by_coordinate.values(), key=_manifest_key))
            return ExpertRegistrySnapshot(self._revision, values)

    def events(self, after_revision: int = 0) -> tuple[ExpertRegistryEvent, ...]:
        if after_revision < 0:
            raise ValueError("after_revision must not be negative")
        with self._lock:
            return tuple(item for item in self._events if item.revision > after_revision)

    def _commit(
        self,
        updated: dict[ExpertPackageCoordinate, ExpertManifest],
        event: ExpertRegistryEvent,
    ) -> None:
        values = tuple(sorted(updated.values(), key=_manifest_key))
        self._by_coordinate = updated
        self._by_expert = _group(values, lambda item: item.expert_id)
        self._by_capability = _capability_index(values)
        self._by_publisher = _group(values, lambda item: item.package.publisher_id)
        self._revision = event.revision
        self._events.append(event)


def _validated_catalog(
    manifests: Iterable[ExpertManifest],
) -> dict[ExpertPackageCoordinate, ExpertManifest]:
    catalog: dict[ExpertPackageCoordinate, ExpertManifest] = {}
    for manifest in manifests:
        if not isinstance(manifest, ExpertManifest):
            raise ValueError("local expert registry requires current ExpertManifest values")
        coordinate = coordinate_for(manifest)
        if coordinate in catalog:
            raise ValueError("duplicate expert package coordinate")
        catalog[coordinate] = manifest
    return catalog


def _group(
    values: tuple[ExpertManifest, ...],
    key: Callable[[ExpertManifest], str],
) -> dict[str, tuple[ExpertManifest, ...]]:
    groups: dict[str, list[ExpertManifest]] = {}
    for value in values:
        groups.setdefault(key(value), []).append(value)
    return {name: tuple(items) for name, items in groups.items()}


def _capability_index(
    values: tuple[ExpertManifest, ...],
) -> dict[str, tuple[ExpertManifest, ...]]:
    groups: dict[str, list[ExpertManifest]] = {}
    for value in values:
        for capability in value.capabilities:
            groups.setdefault(capability, []).append(value)
    return {name: tuple(items) for name, items in groups.items()}


def _require_text(value: str, name: str) -> str:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value
