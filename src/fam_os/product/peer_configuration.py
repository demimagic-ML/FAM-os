"""Owner-private atomic storage for peer listener configuration."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from fam_os.fabric.service_configuration import (
    PeerServiceConfiguration,
    disabled_peer_configuration,
)
from fam_os.schemas import dumps_document, loads_document


class PeerConfigurationStore:
    def __init__(self, path: Path, owner_uid: int) -> None:
        self._path = path
        self._owner_uid = owner_uid

    def load(self) -> PeerServiceConfiguration:
        if not self._path.exists() and not self._path.is_symlink():
            return disabled_peer_configuration()
        _verify_private_file(self._path, self._owner_uid)
        value = loads_document(self._path.read_text("utf-8"))
        if not isinstance(value, PeerServiceConfiguration):
            raise TypeError("peer configuration has an unexpected contract")
        return value

    def put(self, configuration: PeerServiceConfiguration) -> None:
        _prepare_parent(self._path.parent, self._owner_uid)
        if self._path.is_symlink():
            raise OSError("peer configuration cannot replace a symbolic link")
        temporary = self._path.with_name(self._path.name + ".new")
        temporary.unlink(missing_ok=True)
        descriptor = os.open(
            temporary,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        content = (dumps_document(configuration) + "\n").encode("utf-8")
        try:
            if os.write(descriptor, content) != len(content):
                raise OSError("short peer configuration write")
            os.fsync(descriptor)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            os.close(descriptor)
        os.replace(temporary, self._path)
        _fsync_directory(self._path.parent)
        _verify_private_file(self._path, self._owner_uid)


def _prepare_parent(path: Path, owner_uid: int) -> None:
    if path.is_symlink():
        raise OSError("peer configuration parent cannot be a symbolic link")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    metadata = path.stat(follow_symlinks=False)
    if metadata.st_uid != owner_uid or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise PermissionError("peer configuration parent has unsafe ownership or mode")


def _verify_private_file(path: Path, owner_uid: int) -> None:
    metadata = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise OSError("peer configuration must be one regular file")
    if metadata.st_uid != owner_uid or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PermissionError("peer configuration has unsafe ownership or mode")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
