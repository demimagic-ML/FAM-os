"""Owner-initiated export of public trust material for the network broker."""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from fam_os.fabric import PersistentDeviceIdentityStore


NETWORK_AUTHORITY_EXPORT_VERSION = "fam.product.network-authority-export/v1alpha1"


@dataclass(frozen=True, slots=True)
class NetworkAuthorityExport:
    root: Path
    key_id: str
    public_key_path: Path
    manifest_path: Path


def export_network_authority(
    output_root: Path, *, identity_root: Path, display_name: str, owner_uid: int,
) -> NetworkAuthorityExport:
    """Create a new non-secret handoff bundle without mutating host policy."""
    if not output_root.is_absolute() or output_root.exists() or output_root.is_symlink():
        raise ValueError("network authority export root must be a new absolute path")
    credentials = PersistentDeviceIdentityStore(identity_root, owner_uid).resolve(
        display_name,
    )
    public_key = credentials.identity_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    key_path, manifest_path = (
        output_root / "network-authority.pem",
        output_root / "network-authority.json",
    )
    output_root.mkdir(mode=0o700)
    created = []
    try:
        _exclusive(key_path, public_key); created.append(key_path)
        manifest = {
            "contract_version": NETWORK_AUTHORITY_EXPORT_VERSION,
            "key_id": credentials.identity.device_id,
            "owner_uid": owner_uid,
            "public_key_sha256": hashlib.sha256(public_key).hexdigest(),
        }
        _exclusive(
            manifest_path,
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
        )
        created.append(manifest_path)
    except BaseException:
        for path in reversed(created): path.unlink(missing_ok=True)
        output_root.rmdir()
        raise
    return NetworkAuthorityExport(
        output_root, credentials.identity.device_id, key_path, manifest_path,
    )


def _exclusive(path, content):
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
    )
    try:
        if os.write(descriptor, content) != len(content):
            raise OSError("short network authority export write")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
