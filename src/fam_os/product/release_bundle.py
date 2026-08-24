"""Portable signed complete-release bundle construction and loading."""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.product.update_contracts import (
    ComponentKind,
    ReleaseComponent,
    SignedReleaseManifest,
)
from fam_os.product.update_signing import sign_manifest
from fam_os.schemas import dumps_document, loads_document


@dataclass(frozen=True, slots=True)
class ReleaseBundleInput:
    kind: ComponentKind
    name: str
    path: Path

    def __post_init__(self) -> None:
        if not self.name or Path(self.name).name != self.name:
            raise ValueError("bundle component name must be one safe path component")


class ReleaseBundleBuilder:
    def __init__(self, key_id: str, private_key: Ed25519PrivateKey) -> None:
        if not key_id.strip():
            raise ValueError("release signing key ID must not be empty")
        self._key_id = key_id
        self._private_key = private_key

    def build(
        self,
        release_id: str,
        inputs: tuple[ReleaseBundleInput, ...],
        output: Path,
    ) -> SignedReleaseManifest:
        _validate_inputs(inputs)
        if output.exists():
            raise FileExistsError("release bundle output already exists")
        output.mkdir(parents=True, mode=0o700)
        components = tuple(self._copy(item, output) for item in inputs)
        manifest = sign_manifest(release_id, components, self._key_id, self._private_key)
        manifest_path = output / "manifest.json"
        manifest_path.write_text(dumps_document(manifest) + "\n", encoding="utf-8")
        os.chmod(manifest_path, 0o400)
        return manifest

    def _copy(self, item: ReleaseBundleInput, output: Path) -> ReleaseComponent:
        if item.path.is_symlink() or not item.path.is_file():
            raise ValueError("release input must be a regular non-symlink file")
        relative = Path("components") / item.kind.value / item.name
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(item.path, target, follow_symlinks=False)
        os.chmod(target, 0o400)
        return ReleaseComponent(item.kind, item.name, str(relative), _sha256(target))


def load_release_bundle(path: Path) -> SignedReleaseManifest:
    if path.is_symlink() or not path.is_dir():
        raise ValueError("release bundle must be a regular directory")
    manifest_path = path / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("release bundle manifest is missing or unsafe")
    value = loads_document(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(value, SignedReleaseManifest):
        raise TypeError("bundle manifest has an unexpected contract")
    return value


def _validate_inputs(inputs: tuple[ReleaseBundleInput, ...]) -> None:
    kinds = tuple(item.kind for item in inputs)
    identities = tuple((item.kind, item.name) for item in inputs)
    if set(kinds) != set(ComponentKind):
        raise ValueError("complete release bundle requires every component kind")
    if len(set(identities)) != len(identities):
        raise ValueError("release bundle component identities must be unique")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
