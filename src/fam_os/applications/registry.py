"""Atomic dynamic Application Capability Registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from threading import Lock
from uuid import uuid4

from fam_os.applications.capabilities import CapabilityRegistryEntry
from fam_os.applications.connectors import ConnectorRegistration
from fam_os.applications.identifiers import require_identifier


class RegistryEventKind(StrEnum):
    REGISTERED = "registered"
    REPLACED = "replaced"
    REMOVED = "removed"
    AVAILABILITY_CHANGED = "availability_changed"


@dataclass(frozen=True, slots=True)
class CapabilityRegistryEvent:
    event_id: str
    revision: int
    kind: RegistryEventKind
    connector_id: str
    occurred_at: datetime
    instance_id: str | None = None
    capability_id: str | None = None
    available: bool | None = None

    def __post_init__(self) -> None:
        require_identifier(self.event_id, "event_id")
        require_identifier(self.connector_id, "connector_id")
        if self.revision <= 0:
            raise ValueError("registry event revision must be positive")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("registry event time must be timezone-aware")
        for name in ("instance_id", "capability_id"):
            value = getattr(self, name)
            if value is not None:
                require_identifier(value, name)
        if self.kind is RegistryEventKind.AVAILABILITY_CHANGED:
            if self.instance_id is None or self.capability_id is None:
                raise ValueError("availability event requires instance and capability")
            if not isinstance(self.available, bool):
                raise ValueError("availability event requires boolean state")
        elif self.available is not None:
            raise ValueError("only availability events carry availability")


@dataclass(frozen=True, slots=True)
class CapabilityRegistrySnapshot:
    revision: int
    registrations: tuple[ConnectorRegistration, ...]
    entries: tuple[CapabilityRegistryEntry, ...]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier() -> str:
    return str(uuid4())


@dataclass(slots=True)
class ApplicationCapabilityRegistry:
    clock: Callable[[], datetime] = _utc_now
    event_id_factory: Callable[[], str] = _identifier
    _registrations: dict[str, ConnectorRegistration] = field(default_factory=dict)
    _by_instance_capability: dict[tuple[str, str], CapabilityRegistryEntry] = field(default_factory=dict)
    _by_entry_id: dict[str, CapabilityRegistryEntry] = field(default_factory=dict)
    _events: list[CapabilityRegistryEvent] = field(default_factory=list)
    _revision: int = 0
    _lock: Lock = field(default_factory=Lock)

    def register(self, registration: ConnectorRegistration) -> None:
        if not isinstance(registration, ConnectorRegistration):
            raise ValueError("registry requires a ConnectorRegistration")
        with self._lock:
            self._require_no_foreign_collisions(registration)
            kind = (
                RegistryEventKind.REPLACED
                if registration.connector_id in self._registrations
                else RegistryEventKind.REGISTERED
            )
            updated = dict(self._registrations)
            updated[registration.connector_id] = registration
            self._commit(updated, kind, registration.connector_id)

    def unregister(self, connector_id: str) -> None:
        require_identifier(connector_id, "connector_id")
        with self._lock:
            if connector_id not in self._registrations:
                return
            updated = dict(self._registrations)
            del updated[connector_id]
            self._commit(updated, RegistryEventKind.REMOVED, connector_id)

    def entries(self, instance_id: str | None = None) -> tuple[CapabilityRegistryEntry, ...]:
        with self._lock:
            values = tuple(self._by_instance_capability.values())
        if instance_id is not None:
            require_identifier(instance_id, "instance_id")
            values = tuple(item for item in values if item.instance_id == instance_id)
        return tuple(sorted(values, key=_entry_key))

    def lookup(self, instance_id: str, capability_id: str) -> CapabilityRegistryEntry | None:
        key = (
            require_identifier(instance_id, "instance_id"),
            require_identifier(capability_id, "capability_id"),
        )
        with self._lock:
            return self._by_instance_capability.get(key)

    def set_availability(
        self, connector_id: str, instance_id: str, capability_id: str, available: bool
    ) -> None:
        connector_id = require_identifier(connector_id, "connector_id")
        instance_id = require_identifier(instance_id, "instance_id")
        capability_id = require_identifier(capability_id, "capability_id")
        if not isinstance(available, bool):
            raise ValueError("available must be boolean")
        key = (instance_id, capability_id)
        with self._lock:
            entry = self._by_instance_capability.get(key)
            if entry is None or entry.connector_id != connector_id:
                raise KeyError("registry capability is unavailable")
            if entry.available is available:
                return
            registration = self._registrations[connector_id]
            changed = replace(entry, available=available)
            capabilities = tuple(
                changed if item.entry_id == entry.entry_id else item
                for item in registration.capabilities
            )
            updated = dict(self._registrations)
            updated[connector_id] = replace(registration, capabilities=capabilities)
            self._commit(
                updated, RegistryEventKind.AVAILABILITY_CHANGED, connector_id,
                instance_id, capability_id, available,
            )

    def snapshot(self) -> CapabilityRegistrySnapshot:
        with self._lock:
            registrations = tuple(sorted(
                self._registrations.values(), key=lambda item: item.connector_id
            ))
            entries = tuple(sorted(self._by_instance_capability.values(), key=_entry_key))
            return CapabilityRegistrySnapshot(self._revision, registrations, entries)

    def events(self, after_revision: int = 0) -> tuple[CapabilityRegistryEvent, ...]:
        if after_revision < 0:
            raise ValueError("after_revision must not be negative")
        with self._lock:
            return tuple(event for event in self._events if event.revision > after_revision)

    def _require_no_foreign_collisions(self, registration) -> None:
        owner = registration.connector_id
        for entry in registration.capabilities:
            existing = self._by_entry_id.get(entry.entry_id)
            if existing is not None and existing.connector_id != owner:
                raise ValueError("capability entry ID belongs to another connector")
            existing = self._by_instance_capability.get((entry.instance_id, entry.capability_id))
            if existing is not None and existing.connector_id != owner:
                raise ValueError("instance capability belongs to another connector")
        for current in self._registrations.values():
            if current.connector_id != owner and current.instance.instance_id == registration.instance.instance_id:
                raise ValueError("application instance belongs to another connector")

    def _commit(
        self, registrations, kind, connector_id,
        instance_id=None, capability_id=None, available=None,
    ) -> None:
        entries = tuple(
            entry for registration in registrations.values()
            for entry in registration.capabilities
        )
        revision = self._revision + 1
        event = CapabilityRegistryEvent(
            self.event_id_factory(), revision, kind, connector_id,
            self.clock(), instance_id, capability_id, available,
        )
        self._registrations = registrations
        self._by_entry_id = {entry.entry_id: entry for entry in entries}
        self._by_instance_capability = {
            (entry.instance_id, entry.capability_id): entry for entry in entries
        }
        self._revision = revision
        self._events.append(event)


def _entry_key(entry):
    return entry.instance_id, entry.capability_id, entry.entry_id
