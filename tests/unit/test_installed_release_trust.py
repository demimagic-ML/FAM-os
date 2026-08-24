import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.product.atomic_update import AtomicReleaseManager
from fam_os.product.release_trust import verify_installed_release
from fam_os.product.update_contracts import ComponentKind, ReleaseComponent
from fam_os.product.update_signing import sign_manifest


class InstalledReleaseTrustTests(unittest.TestCase):
    def test_runtime_reverifies_manifest_signature_and_component_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = Ed25519PrivateKey.generate()
            manifest = _manifest(root, key)
            manager = AtomicReleaseManager(root / "installed", {"key": key.public_key()})
            manager.apply(manifest, lambda _path: True)
            trust = root / "installed/trust"
            trust.mkdir()
            public = trust / "key.pem"
            public.write_bytes(key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ))
            release = (root / "installed/active").resolve()
            self.assertEqual(manifest, verify_installed_release(release, trust))

            component = release / "expert/payload"
            os.chmod(component, 0o600)
            component.write_text("tampered")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                verify_installed_release(release, trust)


def _manifest(root, key):
    components = []
    for kind in ComponentKind:
        source = root / f"source-{kind.value}"
        source.write_text(kind.value)
        components.append(ReleaseComponent(
            kind, "payload", str(source),
            hashlib.sha256(source.read_bytes()).hexdigest(),
        ))
    return sign_manifest("v1", tuple(components), "key", key)


if __name__ == "__main__":
    unittest.main()
