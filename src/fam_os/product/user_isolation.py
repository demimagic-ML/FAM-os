"""Linux-owner-bound private runtime roots."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class UserRuntimeIdentity:
    user_id: str
    uid: int

    def __post_init__(self) -> None:
        if not self.user_id or self.uid < 0:
            raise ValueError("runtime identity requires a user ID and UID")


class PrivateUserRuntime:
    def __init__(self, root: Path, identity: UserRuntimeIdentity) -> None:
        self._root = root
        self._identity = identity

    def initialize(self) -> Path:
        if self._identity.uid != os.geteuid():
            raise PermissionError("runtime may initialize only for the effective UID")
        if self._root.is_symlink():
            raise OSError("user runtime root cannot be a symlink")
        self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self._root, 0o700)
        self.verify()
        for name in ("state", "memory", "audit", "releases", "recovery"):
            child = self._root / name
            child.mkdir(mode=0o700, exist_ok=True)
            os.chmod(child, 0o700)
        return self._root

    def verify(self) -> None:
        metadata = self._root.stat(follow_symlinks=False)
        if metadata.st_uid != self._identity.uid:
            raise PermissionError("user runtime root has the wrong owner")
        if stat.S_IMODE(metadata.st_mode) != 0o700:
            raise PermissionError("user runtime root must use mode 0700")
        if not stat.S_ISDIR(metadata.st_mode):
            raise OSError("user runtime root must be a directory")

    def private_path(self, area: str, name: str) -> Path:
        if area not in {"state", "memory", "audit", "releases", "recovery"}:
            raise ValueError("unknown private runtime area")
        if not name or Path(name).name != name:
            raise ValueError("private path name must be one safe component")
        self.verify()
        return self._root / area / name
