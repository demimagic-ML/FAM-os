"""Bubblewrap projection for allowlisted service filesystem and device grants."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fam_os.supervisor import (
    AccessApplicationEvidence,
    AccessEvidenceStatus,
    AccessMode,
    AccessResourceDescriptor,
    AccessResourceKind,
    ServiceAccessGrant,
    ServiceDefinition,
)
from fam_os.supervisor.errors import SupervisorAuthorizationError


_PRECREATED_DIRECTORIES = frozenset(("/", "/dev", "/proc", "/tmp"))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_absolute_path(value: str) -> bool:
    path = Path(value)
    return path.is_absolute() and ".." not in path.parts and not _has_control(value)


def _has_control(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


@dataclass(frozen=True, slots=True)
class BubblewrapAccessResource:
    resource_id: str
    kind: AccessResourceKind
    source_path: Path
    sandbox_path: Path

    def __post_init__(self) -> None:
        for path in (self.source_path, self.sandbox_path):
            if (
                not path.is_absolute() or _has_control(str(path))
                or ".." in path.parts
            ):
                raise ValueError("Bubblewrap access paths must be safe absolute paths")
        _validate_destination(self.kind, self.source_path, self.sandbox_path)


@dataclass(frozen=True, slots=True)
class BubblewrapServiceAccessSettings:
    executable: str = "/usr/bin/bwrap"
    runtime_read_only_paths: tuple[str, ...] = ("/usr", "/lib")
    optional_runtime_paths: tuple[str, ...] = ("/lib64",)

    def __post_init__(self) -> None:
        paths = (
            self.executable, *self.runtime_read_only_paths,
            *self.optional_runtime_paths,
        )
        if any(not _safe_absolute_path(value) for value in paths):
            raise ValueError("Bubblewrap settings require safe absolute paths")
        runtime_paths = self.runtime_read_only_paths + self.optional_runtime_paths
        if len(set(runtime_paths)) != len(runtime_paths):
            raise ValueError("Bubblewrap runtime paths must be unique")


@dataclass(slots=True)
class BubblewrapServiceAccessAdapter:
    resources: tuple[BubblewrapAccessResource, ...]
    settings: BubblewrapServiceAccessSettings = BubblewrapServiceAccessSettings()
    clock: Callable[[], datetime] = _utc_now
    _active: dict[str, ServiceAccessGrant] = field(default_factory=dict)
    _by_id: dict[str, BubblewrapAccessResource] = field(init=False)

    def __post_init__(self) -> None:
        self._by_id = {item.resource_id: item for item in self.resources}
        if not self.resources or len(self._by_id) != len(self.resources):
            raise ValueError("Bubblewrap access resources must be non-empty and unique")
        destinations = {item.sandbox_path for item in self.resources}
        if len(destinations) != len(self.resources):
            raise ValueError("Bubblewrap sandbox destinations must be unique")

    def grant(
        self, grant: ServiceAccessGrant, resource: AccessResourceDescriptor
    ) -> AccessApplicationEvidence:
        configured = self._require_mapping(grant, resource)
        _binding_flag(grant.mode, configured.kind)
        current = self._active.get(grant.grant_id)
        if current is not None and current != grant:
            raise SupervisorAuthorizationError("Bubblewrap grant ID conflicts")
        self._active[grant.grant_id] = grant
        return self._evidence(grant, AccessEvidenceStatus.GRANTED)

    def revoke(
        self, grant: ServiceAccessGrant, resource: AccessResourceDescriptor
    ) -> AccessApplicationEvidence:
        self._require_mapping(grant, resource)
        self._active.pop(grant.grant_id, None)
        return self._evidence(grant, AccessEvidenceStatus.REVOKED)

    def project(self, definition: ServiceDefinition) -> ServiceDefinition:
        instant = self.clock()
        grants = tuple(
            grant
            for grant in self._active.values()
            if grant.service_id == definition.service_id and grant.active_at(instant)
        )
        command = _bubblewrap_command(definition.command, grants, self._by_id, self.settings)
        return ServiceDefinition(
            definition.service_id, command, definition.environment, definition.limits
        )

    def _require_mapping(
        self, grant: ServiceAccessGrant, resource: AccessResourceDescriptor
    ) -> BubblewrapAccessResource:
        configured = self._by_id.get(resource.resource_id)
        if configured is None or configured.kind is not resource.kind:
            raise SupervisorAuthorizationError("access resource has no Bubblewrap mapping")
        if grant.resource_id != configured.resource_id or grant.kind is not configured.kind:
            raise SupervisorAuthorizationError("grant does not match Bubblewrap mapping")
        return configured

    def _evidence(
        self, grant: ServiceAccessGrant, status: AccessEvidenceStatus
    ) -> AccessApplicationEvidence:
        return AccessApplicationEvidence(
            grant.grant_id,
            grant.service_id,
            grant.resource_id,
            "bubblewrap.service-access.v1",
            status,
            self.clock(),
        )


def _bubblewrap_command(
    service_command: tuple[str, ...],
    grants: tuple[ServiceAccessGrant, ...],
    resources: dict[str, BubblewrapAccessResource],
    settings: BubblewrapServiceAccessSettings,
) -> tuple[str, ...]:
    command = [
        settings.executable,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--cap-drop",
        "ALL",
    ]
    for path in settings.runtime_read_only_paths:
        command.extend(("--ro-bind", path, path))
    for path in settings.optional_runtime_paths:
        command.extend(("--ro-bind-try", path, path))
    command.extend(("--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"))
    _append_bindings(command, grants, resources)
    command.extend(("--chdir", "/tmp", "--", *service_command))
    return tuple(command)


def _append_bindings(
    command: list[str],
    grants: tuple[ServiceAccessGrant, ...],
    resources: dict[str, BubblewrapAccessResource],
) -> None:
    created: set[str] = set(_PRECREATED_DIRECTORIES)
    for grant in grants:
        resource = resources[grant.resource_id]
        _append_destination_directories(command, resource.sandbox_path, created)
        command.extend(
            (
                _binding_flag(grant.mode, resource.kind),
                str(resource.source_path),
                str(resource.sandbox_path),
            )
        )


def _append_destination_directories(
    command: list[str], sandbox_path: Path, created: set[str]
) -> None:
    parents = tuple(reversed(sandbox_path.parents[:-1]))
    for parent in parents:
        path = str(parent)
        if path not in created:
            command.extend(("--dir", path))
            created.add(path)


def _binding_flag(mode: AccessMode, kind: AccessResourceKind) -> str:
    if mode is AccessMode.WRITE:
        raise SupervisorAuthorizationError("Bubblewrap cannot enforce write-only access")
    if kind is AccessResourceKind.DEVICE and mode is AccessMode.READ_WRITE:
        return "--dev-bind"
    return "--ro-bind" if mode is AccessMode.READ else "--bind"


def _validate_destination(kind: AccessResourceKind, source: Path, target: Path) -> None:
    if kind is AccessResourceKind.FILESYSTEM and not target.is_relative_to("/access"):
        raise ValueError("filesystem grants must be projected below /access")
    if kind is AccessResourceKind.DEVICE:
        if not source.is_relative_to("/dev") or not target.is_relative_to("/dev"):
            raise ValueError("device grants must map device-tree paths")
    if target in {Path("/access"), Path("/dev")}:
        raise ValueError("access grants cannot replace a sandbox root")

