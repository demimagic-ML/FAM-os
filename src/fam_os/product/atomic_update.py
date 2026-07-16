"""Atomic release-set staging, activation, and rollback."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Callable
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.product.update_contracts import SignedReleaseManifest, UpdateReceipt
from fam_os.product.update_signing import verify_manifest


class AtomicReleaseManager:
    def __init__(self, root: Path, trusted_keys: dict[str, Ed25519PublicKey]) -> None:
        self._root = root
        self._trusted_keys = trusted_keys

    def apply(
        self, manifest: SignedReleaseManifest, health_check: Callable[[Path], bool]
    ) -> UpdateReceipt:
        previous = self.active_release_id()
        staging = self._root / ".staging" / f"{manifest.release_id}-{uuid4().hex}"
        try:
            self._verify_signature(manifest)
            self._stage(manifest, staging)
            if not health_check(staging):
                return UpdateReceipt(manifest.release_id, previous, True, False, False,
                                     False, previous, "health_check_failed")
            destination = self._root / "releases" / manifest.release_id
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise FileExistsError("release ID is immutable")
            os.replace(staging, destination)
            self._switch_active(destination)
            return UpdateReceipt(manifest.release_id, previous, True, True, True,
                                 False, manifest.release_id, "activated")
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def rollback(self, release_id: str, health_check: Callable[[Path], bool]) -> UpdateReceipt:
        previous = self.active_release_id()
        target = self._root / "releases" / release_id
        if not target.is_dir() or not health_check(target):
            raise ValueError("rollback target is missing or unhealthy")
        self._switch_active(target)
        return UpdateReceipt(release_id, previous, True, True, True, True,
                             release_id, "rolled_back")

    def active_release_id(self) -> str | None:
        active = self._root / "active"
        if not active.is_symlink():
            return None
        target = Path(os.readlink(active))
        return target.name

    def _verify_signature(self, manifest: SignedReleaseManifest) -> None:
        key = self._trusted_keys.get(manifest.signer_key_id)
        if key is None:
            raise ValueError("release signer is not trusted")
        verify_manifest(manifest, key)

    def _stage(self, manifest: SignedReleaseManifest, staging: Path) -> None:
        staging.mkdir(parents=True, mode=0o700)
        for component in manifest.components:
            source = Path(component.source_path)
            if source.is_symlink() or not source.is_file():
                raise ValueError("release source must be a regular non-symlink file")
            if _sha256(source) != component.sha256:
                raise ValueError("release component digest mismatch")
            target = staging / component.kind.value / component.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target, follow_symlinks=False)
            os.chmod(target, 0o400)

    def _switch_active(self, destination: Path) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        temporary = self._root / f".active-{uuid4().hex}"
        temporary.symlink_to(destination.relative_to(self._root))
        os.replace(temporary, self._root / "active")
        _fsync(self._root)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fsync(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
