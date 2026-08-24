"""Build one signed release and install it into two isolated prefixes."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.product.bundle_installation import SignedBundleInstallation
from fam_os.product.release_assembly import CompleteReleaseAssembler
from fam_os.product.update_contracts import SignedReleaseManifest


@dataclass(frozen=True, slots=True)
class PeerExitInstallations:
    desktop: SignedBundleInstallation
    server: SignedBundleInstallation
    manifest: SignedReleaseManifest
    trusted_key_path: Path
    key_id: str


def build_and_install_pair(repository: Path, root: Path) -> PeerExitInstallations:
    wheelhouse = root / "wheelhouse"
    wheelhouse.mkdir()
    subprocess.run(
        (
            sys.executable, "-m", "pip", "wheel", str(repository),
            "--wheel-dir", str(wheelhouse), "--no-build-isolation",
        ),
        check=True, capture_output=True, text=True, timeout=300,
    )
    key_id = "phase21-peer-test"
    private_key = Ed25519PrivateKey.generate()
    bundle = root / "release"
    manifest = CompleteReleaseAssembler(repository).build(
        "phase21-peer-exit", wheelhouse, bundle, key_id, private_key,
    )
    trusted_key = root / "trusted-key.pem"
    trusted_key.write_bytes(private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    trusted_key.chmod(0o600)
    desktop = _install(root / "desktop-install", bundle, key_id, private_key)
    server = _install(root / "server-install", bundle, key_id, private_key)
    return PeerExitInstallations(desktop, server, manifest, trusted_key, key_id)


def _install(root, bundle, key_id, private_key) -> SignedBundleInstallation:
    installation = SignedBundleInstallation(root, {key_id: private_key.public_key()})
    receipt = installation.install(bundle)
    if not receipt.healthy:
        raise RuntimeError(f"signed peer release installation failed: {receipt.issues}")
    return installation
