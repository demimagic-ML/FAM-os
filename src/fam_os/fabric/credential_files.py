"""Owner-private filesystem primitives for persistent device credentials."""

from __future__ import annotations

import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class UnsafeDeviceCredential(OSError):
    """Raised when credential storage is incomplete, linked, or misowned."""


@contextmanager
def identity_lock(path: Path, owner_uid: int) -> Iterator[None]:
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        _verify_private_descriptor(descriptor, owner_uid)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def create_private_credential(path: Path, content: bytes) -> None:
    descriptor = os.open(
        path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600,
    )
    try:
        if os.write(descriptor, content) != len(content):
            raise OSError("short device credential write")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def prepare_identity_root(path: Path, owner_uid: int) -> None:
    if path.is_symlink():
        raise UnsafeDeviceCredential("device identity root is a symbolic link")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    metadata = path.stat(follow_symlinks=False)
    if metadata.st_uid != owner_uid or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise UnsafeDeviceCredential("device identity root has unsafe ownership or mode")


def verify_private_credential(path: Path, owner_uid: int) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        _verify_private_descriptor(descriptor, owner_uid)
    finally:
        os.close(descriptor)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _verify_private_descriptor(descriptor: int, owner_uid: int) -> None:
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise UnsafeDeviceCredential("device credential must be one regular file")
    if metadata.st_uid != owner_uid or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise UnsafeDeviceCredential("device credential has unsafe ownership or mode")
