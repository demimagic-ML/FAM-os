"""Build one signed candidate and install that exact bundle repeatedly."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.product.bundle_installation import SignedBundleInstallation
from fam_os.product.release_assembly import CompleteReleaseAssembler
from fam_os.product.update_contracts import SignedReleaseManifest


@dataclass(slots=True)
class InstalledCandidate:
    root: Path
    bundle: Path
    manifest: SignedReleaseManifest
    private_key: Ed25519PrivateKey
    trusted_key_path: Path
    wheel_sha256: str
    manifest_sha256: str
    installations: list[SignedBundleInstallation] = field(default_factory=list)

    @property
    def key_id(self) -> str:
        return self.manifest.signer_key_id

    def install(self, name: str) -> SignedBundleInstallation:
        prefix = self.root / "installations" / name
        installation = SignedBundleInstallation(
            prefix, {self.key_id: self.private_key.public_key()},
        )
        receipt = installation.install(self.bundle)
        if not receipt.healthy or receipt.release_id != self.manifest.release_id:
            raise RuntimeError(f"candidate installation failed: {receipt.issues}")
        installed_manifest = prefix / "active/release-manifest.json"
        if _sha256(installed_manifest) != self.manifest_sha256:
            raise RuntimeError("installed candidate manifest identity changed")
        self.installations.append(installation)
        return installation

    def remove_all(self) -> bool:
        for installation in reversed(self.installations):
            if installation.prefix.exists():
                installation.remove()
        return all(not item.prefix.exists() for item in self.installations)


def build_candidate(repository: Path, root: Path, run_id: str) -> InstalledCandidate:
    root.mkdir(parents=True, mode=0o700)
    wheelhouse = root / "wheelhouse"
    wheelhouse.mkdir()
    with (root / "wheel-build.log").open("w", encoding="utf-8") as log:
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
        raise RuntimeError("candidate build did not produce exactly one FAM_OS wheel")
    private_key = Ed25519PrivateKey.generate()
    key_id = f"phase23-{run_id}"
    bundle = root / "release"
    manifest = CompleteReleaseAssembler(repository).build(
        f"fam-os-{run_id}", wheelhouse, bundle, key_id, private_key,
    )
    trusted_key = root / "trusted-key.pem"
    trusted_key.write_bytes(private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    trusted_key.chmod(0o400)
    return InstalledCandidate(
        root, bundle, manifest, private_key, trusted_key,
        _sha256(wheels[0]), _sha256(bundle / "manifest.json"),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
