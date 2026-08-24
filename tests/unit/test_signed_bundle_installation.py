import os
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.product.bundle_installation import SignedBundleInstallation
from fam_os.product.installed_launcher import (
    installed_launcher, stable_runtime_python,
)


class SignedBundleInstallationTests(unittest.TestCase):
    def test_launcher_uses_stable_runtime_not_builder_virtualenv(self) -> None:
        runtime = stable_runtime_python()
        launcher = installed_launcher(
            Path("/opt/fam-os"), "fam_os.product.service", runtime,
        )

        self.assertIn(f"exec '{runtime}' -m fam_os.product.service", launcher)
        if Path(os.sys.executable).resolve() != Path(runtime):
            self.assertNotIn(os.sys.executable, launcher)

    def test_existing_read_only_trusted_key_is_not_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary)
            key = Ed25519PrivateKey.generate().public_key()
            installation = SignedBundleInstallation(prefix, {"release-key": key})

            installation._write_trusted_keys()
            path = prefix / "trust/release-key.pem"
            original = path.read_bytes()
            self.assertEqual(0o400, path.stat().st_mode & 0o777)

            installation._write_trusted_keys()

            self.assertEqual(original, path.read_bytes())
            self.assertEqual(0o400, path.stat().st_mode & 0o777)
            self.assertEqual(os.geteuid(), path.stat().st_uid)


if __name__ == "__main__":
    unittest.main()
