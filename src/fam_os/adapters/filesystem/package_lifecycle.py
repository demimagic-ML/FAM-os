"""Durable atomic lifecycle state and immutable local package artifacts."""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fam_os.experts.registry_contracts import ExpertPackageCoordinate
from fam_os.registry.lifecycle_contracts import (
    ExpertPackageInstallationState,
    empty_installation_state,
)
from fam_os.registry.package import ArtifactDigest
from fam_os.schemas import dumps_document, loads_document


_SAFE_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}\Z")


class JsonPackageLifecycleStateStore:
    """Cross-process CAS store using flock, fsync, and atomic replacement."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock_path = path.with_suffix(path.suffix + ".lock")
        self._thread_lock = Lock()

    def load(self) -> ExpertPackageInstallationState:
        with self._locked():
            return self._load_unlocked()

    def commit(self, expected_revision: int, state: ExpertPackageInstallationState) -> None:
        if state.revision != expected_revision + 1:
            raise ValueError("committed lifecycle state must advance exactly one revision")
        with self._locked():
            current = self._load_unlocked()
            if current.revision != expected_revision:
                raise RuntimeError("package lifecycle state changed concurrently")
            self._write_unlocked(dumps_document(state).encode("utf-8"))

    def _load_unlocked(self) -> ExpertPackageInstallationState:
        if not self._path.exists():
            return empty_installation_state()
        if self._path.is_symlink():
            raise OSError("package lifecycle state cannot be a symlink")
        value = loads_document(self._path.read_text(encoding="utf-8"))
        if not isinstance(value, ExpertPackageInstallationState):
            raise ValueError("package lifecycle state file has the wrong document type")
        return value

    def _write_unlocked(self, content: bytes) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(f".{self._path.name}.{uuid4().hex}.tmp")
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._path)
            _fsync_directory(self._path.parent)
        finally:
            temporary.unlink(missing_ok=True)

    @contextmanager
    def _locked(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._thread_lock:
            descriptor = os.open(
                self._lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
            )
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)


class ImmutablePackageArtifactStore:
    """No-follow, digest-checked artifact copy into coordinate-owned paths."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def install(
        self,
        coordinate: ExpertPackageCoordinate,
        source_locator: str,
        expected_digest: ArtifactDigest,
    ) -> str:
        if expected_digest.algorithm != "sha256":
            raise ValueError("artifact store supports SHA-256 only")
        destination = self._destination(coordinate)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            _require_digest(destination, expected_digest)
            return str(destination.relative_to(self._root))
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        try:
            _copy_verified(Path(source_locator), temporary, expected_digest)
            os.replace(temporary, destination)
            _fsync_directory(destination.parent)
        finally:
            temporary.unlink(missing_ok=True)
        return str(destination.relative_to(self._root))

    def remove(self, artifact_locator: str) -> None:
        destination = self._resolve_locator(artifact_locator)
        destination.unlink(missing_ok=True)
        _fsync_directory(destination.parent)

    def verify(self, artifact_locator: str, expected_digest: ArtifactDigest) -> None:
        _require_digest(self._resolve_locator(artifact_locator), expected_digest)

    def _destination(self, coordinate: ExpertPackageCoordinate) -> Path:
        package_id = _safe_component(coordinate.package_id)
        version = _safe_component(coordinate.package_version)
        parent = self._root / package_id / version
        parent.mkdir(parents=True, exist_ok=True)
        resolved_root = self._root.resolve(strict=False)
        resolved_parent = parent.resolve(strict=True)
        if resolved_parent != resolved_root and resolved_root not in resolved_parent.parents:
            raise ValueError("package artifact path escapes the configured root")
        destination = resolved_parent / "artifact.bin"
        if destination.is_symlink():
            raise OSError("installed artifact cannot be a symlink")
        return destination

    def _resolve_locator(self, locator: str) -> Path:
        relative = Path(locator)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("artifact locator must remain beneath the package root")
        candidate = self._root / relative
        resolved_root = self._root.resolve(strict=False)
        resolved_parent = candidate.parent.resolve(strict=False)
        if resolved_parent != resolved_root and resolved_root not in resolved_parent.parents:
            raise ValueError("artifact locator escapes the package root")
        destination = resolved_parent / candidate.name
        if destination.is_symlink():
            raise OSError("installed artifact cannot be a symlink")
        return destination


def _copy_verified(source: Path, destination: Path, expected: ArtifactDigest) -> None:
    source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    destination_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    digest = hashlib.sha256()
    with os.fdopen(source_fd, "rb") as source_stream, os.fdopen(destination_fd, "wb") as output:
        while chunk := source_stream.read(1024 * 1024):
            digest.update(chunk)
            output.write(chunk)
        output.flush()
        os.fsync(output.fileno())
    if digest.hexdigest() != expected.value:
        destination.unlink(missing_ok=True)
        raise ValueError("installed artifact digest does not match accepted evidence")


def _require_digest(path: Path, expected: ArtifactDigest) -> None:
    if path.is_symlink():
        raise OSError("installed artifact cannot be a symlink")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    digest = hashlib.sha256()
    with os.fdopen(descriptor, "rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != expected.value:
        raise ValueError("existing immutable artifact has unexpected content")


def _safe_component(value: str) -> str:
    if _SAFE_COMPONENT.fullmatch(value) is None:
        raise ValueError("package coordinate is unsafe for local artifact storage")
    return value


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
