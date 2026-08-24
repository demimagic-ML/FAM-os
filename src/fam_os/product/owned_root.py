"""Owner-bound markers for destructible FAM_OS state and runtime roots."""

from __future__ import annotations

import json
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


MARKER = ".fam-os-owned-root.json"
CONTRACT_VERSION = "fam.product.owned-root/v1alpha1"


@dataclass(frozen=True, slots=True)
class OwnedProductRoot:
    path: Path
    purpose: str
    owner_uid: int

    def initialize(self) -> None:
        self._validate_identity()
        marker = self.path / MARKER
        expected = self._document()
        if marker.exists() or marker.is_symlink():
            if marker.is_symlink() or not marker.is_file():
                raise PermissionError("FAM_OS owned-root marker is unsafe")
            if json.loads(marker.read_text(encoding="utf-8")) != expected:
                raise PermissionError("FAM_OS owned-root marker does not match this root")
            self._validate_marker(marker)
            return
        staging = self.path / f".{MARKER}.{uuid4().hex}"
        try:
            staging.write_text(
                json.dumps(expected, sort_keys=True) + "\n", encoding="utf-8",
            )
            os.chmod(staging, 0o600)
            os.replace(staging, marker)
        finally:
            staging.unlink(missing_ok=True)
        self._validate_marker(marker)

    def verify(self) -> None:
        self._validate_identity()
        marker = self.path / MARKER
        if marker.is_symlink() or not marker.is_file():
            raise FileNotFoundError("FAM_OS owned-root marker is missing")
        self._validate_marker(marker)
        if json.loads(marker.read_text(encoding="utf-8")) != self._document():
            raise PermissionError("FAM_OS owned-root marker does not match this root")

    def remove(self) -> bool:
        if not self.path.exists() and not self.path.is_symlink():
            return False
        self.verify()
        shutil.rmtree(self.path)
        return True

    def _validate_identity(self) -> None:
        if self.purpose not in {"state", "runtime"}:
            raise ValueError("FAM_OS owned-root purpose is invalid")
        resolved = self.path.resolve()
        if not self.path.is_absolute() or resolved == Path("/") or len(resolved.parts) < 3:
            raise ValueError("refusing unsafe FAM_OS owned-root path")
        metadata = self.path.stat(follow_symlinks=False)
        if self.path.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
            raise PermissionError("FAM_OS owned root must be a real directory")
        if metadata.st_uid != self.owner_uid or stat.S_IMODE(metadata.st_mode) != 0o700:
            raise PermissionError("FAM_OS owned root has unsafe owner or mode")

    def _validate_marker(self, marker: Path) -> None:
        metadata = marker.stat(follow_symlinks=False)
        if metadata.st_uid != self.owner_uid or stat.S_IMODE(metadata.st_mode) != 0o600:
            raise PermissionError("FAM_OS owned-root marker has unsafe owner or mode")

    def _document(self) -> dict[str, object]:
        return {
            "contract_version": CONTRACT_VERSION,
            "owner_uid": self.owner_uid,
            "purpose": self.purpose,
            "root": str(self.path.resolve()),
        }
