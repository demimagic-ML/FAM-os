"""Runtime verification of an activated signed release and its components."""

from __future__ import annotations

import hashlib
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.product.update_contracts import SignedReleaseManifest
from fam_os.product.update_signing import verify_manifest
from fam_os.schemas import loads_document


def verify_installed_release(
    release_root: Path,
    trust_root: Path,
) -> SignedReleaseManifest:
    manifest_path = release_root / "release-manifest.json"
    value = loads_document(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(value, SignedReleaseManifest):
        raise ValueError("installed release manifest has the wrong type")
    key_path = trust_root / f"{value.signer_key_id}.pem"
    if key_path.is_symlink() or not key_path.is_file():
        raise FileNotFoundError("installed release trust key is unavailable")
    key = serialization.load_pem_public_key(key_path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("installed release trust key is not Ed25519")
    verify_manifest(value, key)
    for component in value.components:
        path = release_root / component.kind.value / component.name
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError("installed release component is unavailable")
        if _sha256(path) != component.sha256:
            raise ValueError("installed release component digest mismatch")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
