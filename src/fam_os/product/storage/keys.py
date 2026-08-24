"""Fail-closed owner master-key resolution."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class KeyResolutionState(StrEnum):
    READY = "ready"
    RECOVERY_REQUIRED = "recovery_required"


@dataclass(frozen=True, slots=True)
class OwnerMasterKey:
    key_id: str
    key_bytes: bytes

    def __post_init__(self) -> None:
        if len(self.key_bytes) != 32 or self.key_id != _key_id(self.key_bytes):
            raise ValueError("owner master key identity is invalid")


@dataclass(frozen=True, slots=True)
class KeyResolution:
    state: KeyResolutionState
    reason: str
    key: OwnerMasterKey | None

    def __post_init__(self) -> None:
        if (self.state is KeyResolutionState.READY) != (self.key is not None):
            raise ValueError("key resolution state and value disagree")


class OwnerKeyStore:
    def __init__(self, path: Path, owner_uid: int) -> None:
        self._path = path
        self._owner_uid = owner_uid

    def resolve(self, *, database_exists: bool) -> KeyResolution:
        if self._path.exists() or self._path.is_symlink():
            return self._load()
        if database_exists:
            return _recovery("master_key_missing_for_existing_database")
        return self._create()

    def _load(self) -> KeyResolution:
        try:
            _verify_private_file(self._path, self._owner_uid)
            value = self._path.read_bytes()
            key = OwnerMasterKey(_key_id(value), value)
        except (OSError, PermissionError, ValueError):
            return _recovery("master_key_corrupt_or_unsafe")
        return KeyResolution(KeyResolutionState.READY, "master_key_loaded", key)

    def _create(self) -> KeyResolution:
        try:
            _prepare_parent(self._path.parent, self._owner_uid)
            descriptor = os.open(
                self._path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                value = os.urandom(32)
                written = os.write(descriptor, value)
                if written != len(value):
                    raise OSError("short master key write")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            _fsync_directory(self._path.parent)
            _verify_private_file(self._path, self._owner_uid)
            key = OwnerMasterKey(_key_id(value), value)
        except FileExistsError:
            return self._load()
        except (OSError, PermissionError, ValueError):
            self._path.unlink(missing_ok=True)
            return _recovery("master_key_creation_failed")
        return KeyResolution(KeyResolutionState.READY, "master_key_created", key)


def _prepare_parent(path: Path, owner_uid: int) -> None:
    if path.is_symlink():
        raise OSError("master key parent cannot be a symlink")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    metadata = path.stat(follow_symlinks=False)
    if metadata.st_uid != owner_uid or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise PermissionError("master key parent has unsafe owner or mode")


def _verify_private_file(path: Path, owner_uid: int) -> None:
    metadata = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise OSError("master key must be one regular file")
    if metadata.st_uid != owner_uid or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PermissionError("master key has unsafe owner or mode")


def _key_id(value: bytes) -> str:
    return "owner-key-" + hashlib.sha256(value).hexdigest()[:24]


def _recovery(reason: str) -> KeyResolution:
    return KeyResolution(KeyResolutionState.RECOVERY_REQUIRED, reason, None)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
