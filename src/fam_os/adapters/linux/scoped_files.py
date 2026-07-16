"""Scoped deterministic file observation and atomic replacement adapter."""

import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ScopedFilePolicy:
    roots: tuple[Path, ...]
    maximum_read_bytes: int = 4_194_304
    maximum_write_bytes: int = 4_194_304

    def __post_init__(self) -> None:
        if not self.roots or len(set(self.roots)) != len(self.roots):
            raise ValueError("file policy requires unique roots")
        if min(self.maximum_read_bytes, self.maximum_write_bytes) <= 0:
            raise ValueError("file policy byte limits must be positive")
        for root in self.roots:
            if not root.is_absolute() or not root.is_dir() or root.is_symlink():
                raise ValueError("file policy roots must be real absolute directories")

    def authorize(self, path: Path, allow_missing=False) -> Path:
        if not path.is_absolute() or ".." in path.parts:
            raise PermissionError("file path is outside the approved scope")
        root = next((item for item in self.roots if path.is_relative_to(item)), None)
        if root is None:
            raise PermissionError("file path is outside the approved scope")
        if not root.is_dir() or root.is_symlink():
            raise PermissionError("file scope root is no longer trusted")
        _reject_symlinks(root, path, allow_missing)
        return path


@dataclass(frozen=True, slots=True)
class FileObservation:
    path: str
    size_bytes: int
    sha256: str
    content: bytes | None = None


@dataclass(frozen=True, slots=True)
class FileWriteProposal:
    operation_id: str
    path: str
    expected_before_sha256: str | None
    expected_after_sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not self.operation_id.strip() or not self.path:
            raise ValueError("file write proposal identity must not be empty")
        for value in (self.expected_before_sha256, self.expected_after_sha256):
            if value is not None and len(value) != 64:
                raise ValueError("file write proposal hashes must be SHA-256")


@dataclass(frozen=True, slots=True)
class FileMutationEvidence:
    operation_id: str
    path: str
    before_sha256: str | None
    after_sha256: str
    size_bytes: int


class ScopedFileAdapter:
    def __init__(self, policy: ScopedFilePolicy):
        self.policy = policy

    def observe(self, path: Path, include_content=False) -> FileObservation:
        path = self.policy.authorize(path)
        content, details = _read_regular(path, self.policy.maximum_read_bytes)
        return FileObservation(
            str(path), len(content), _sha256(content),
            content if include_content else None,
        )

    def prepare_write(self, operation_id: str, path: Path, content: bytes):
        _require_bytes(content, self.policy.maximum_write_bytes)
        path = self.policy.authorize(path, allow_missing=True)
        before = self._current_hash(path)
        return FileWriteProposal(
            operation_id, str(path), before, _sha256(content), len(content)
        )

    def apply_write(self, proposal: FileWriteProposal, content: bytes):
        _require_bytes(content, self.policy.maximum_write_bytes)
        path = self.policy.authorize(Path(proposal.path), allow_missing=True)
        if len(content) != proposal.size_bytes or _sha256(content) != proposal.expected_after_sha256:
            raise ValueError("file write content does not match its proposal")
        before = self._current_hash(path)
        if before != proposal.expected_before_sha256:
            raise RuntimeError("file write precondition changed")
        _atomic_replace(path, content)
        after = self.observe(path)
        if after.sha256 != proposal.expected_after_sha256:
            raise RuntimeError("file write postcondition failed")
        return FileMutationEvidence(
            proposal.operation_id, str(path), before, after.sha256, after.size_bytes
        )

    def _current_hash(self, path):
        if not path.exists():
            return None
        return self.observe(path).sha256


def _read_regular(path, maximum_bytes):
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_size > maximum_bytes:
            raise ValueError("file is not a bounded regular file")
        content = bytearray()
        while len(content) <= maximum_bytes:
            chunk = os.read(descriptor, min(65_536, maximum_bytes + 1 - len(content)))
            if not chunk:
                return bytes(content), details
            content.extend(chunk)
        raise ValueError("file exceeds the configured read limit")
    finally:
        os.close(descriptor)


def _atomic_replace(path, content):
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    descriptor, temporary = tempfile.mkstemp(prefix=".fam-write-", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _reject_symlinks(root, path, allow_missing):
    current = root
    relative = path.relative_to(root)
    for index, part in enumerate(relative.parts):
        current = current / part
        try:
            details = current.lstat()
        except FileNotFoundError:
            if allow_missing and index == len(relative.parts) - 1:
                return
            raise PermissionError("file scope contains a missing component")
        if stat.S_ISLNK(details.st_mode):
            raise PermissionError("file scope cannot traverse symbolic links")


def _require_bytes(content, maximum_bytes):
    if not isinstance(content, bytes) or len(content) > maximum_bytes:
        raise ValueError("file content exceeds the configured write limit")


def _sha256(content):
    return hashlib.sha256(content).hexdigest()
