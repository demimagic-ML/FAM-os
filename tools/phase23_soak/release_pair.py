"""Build one wheel and two releases for a real signed update/rollback cycle."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from fam_os.product.bundle_installation import SignedBundleInstallation
from fam_os.product.release_assembly import CompleteReleaseAssembler
from fam_os.product.update_contracts import SignedReleaseManifest


@dataclass(frozen=True, slots=True)
class SignedReleasePair:
    root: Path
    base_bundle: Path
    update_bundle: Path
    base_manifest: SignedReleaseManifest
    update_manifest: SignedReleaseManifest
    key_id: str
    public_key_path: Path
    wheel_sha256: str
    base_manifest_sha256: str
    update_manifest_sha256: str

    def installation(self, prefix: Path) -> SignedBundleInstallation:
        return SignedBundleInstallation(prefix, {self.key_id: self.public_key()})

    def public_key(self) -> Ed25519PublicKey:
        key = serialization.load_pem_public_key(self.public_key_path.read_bytes())
        if not isinstance(key, Ed25519PublicKey):
            raise TypeError("soak trust key is not Ed25519")
        return key

    def identity(self) -> dict[str, object]:
        return {
            "base_release_id": self.base_manifest.release_id,
            "update_release_id": self.update_manifest.release_id,
            "signer_key_id": self.key_id,
            "component_count": len(self.base_manifest.components),
            "wheel_sha256": self.wheel_sha256,
            "base_manifest_sha256": self.base_manifest_sha256,
            "update_manifest_sha256": self.update_manifest_sha256,
        }


def build_release_pair(
    repository: Path, root: Path, run_id: str,
) -> SignedReleasePair:
    root.mkdir(parents=True, mode=0o700)
    wheelhouse = root / "wheelhouse"
    wheelhouse.mkdir()
    log_path = root / "wheel-build.log"
    with log_path.open("w", encoding="utf-8") as log:
        subprocess.run(
            (
                sys.executable, "-m", "pip", "wheel", str(repository),
                "--wheel-dir", str(wheelhouse), "--no-build-isolation",
            ),
            check=True, stdout=log, stderr=subprocess.STDOUT, text=True,
            timeout=600,
        )
    wheels = tuple(wheelhouse.glob("fam_os-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("soak build did not produce exactly one FAM_OS wheel")
    private_key = Ed25519PrivateKey.generate()
    key_id = f"phase23-soak-{run_id}"
    assembler = CompleteReleaseAssembler(repository)
    base_bundle = root / "base-release"
    update_bundle = root / "update-release"
    base_manifest = assembler.build(
        f"fam-os-{run_id}-base", wheelhouse, base_bundle, key_id, private_key,
    )
    update_manifest = assembler.build(
        f"fam-os-{run_id}-update", wheelhouse, update_bundle, key_id, private_key,
    )
    public_key_path = root / "trusted-key.pem"
    public_key_path.write_bytes(private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    public_key_path.chmod(0o400)
    return SignedReleasePair(
        root, base_bundle, update_bundle, base_manifest, update_manifest,
        key_id, public_key_path, _sha256(wheels[0]),
        _sha256(base_bundle / "manifest.json"),
        _sha256(update_bundle / "manifest.json"),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
