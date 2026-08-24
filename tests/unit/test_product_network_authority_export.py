import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.product.network_authority_export import (
    NETWORK_AUTHORITY_EXPORT_VERSION, export_network_authority,
)


class ProductNetworkAuthorityExportTests(unittest.TestCase):
    def test_owner_explicit_export_contains_only_public_trust_material(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            credentials = SimpleNamespace(
                identity=SimpleNamespace(device_id="device-owner-1"),
                identity_key=Ed25519PrivateKey.generate(),
            )
            with patch(
                "fam_os.product.network_authority_export."
                "PersistentDeviceIdentityStore"
            ) as store:
                store.return_value.resolve.return_value = credentials
                result = export_network_authority(
                    root / "export", identity_root=root / "identity",
                    display_name="owner device", owner_uid=os.geteuid(),
                )
            manifest = json.loads(result.manifest_path.read_text())
            self.assertEqual(NETWORK_AUTHORITY_EXPORT_VERSION, manifest["contract_version"])
            self.assertEqual("device-owner-1", manifest["key_id"])
            self.assertIn(b"BEGIN PUBLIC KEY", result.public_key_path.read_bytes())
            self.assertNotIn(b"PRIVATE", result.public_key_path.read_bytes())
            self.assertEqual(0o700, result.root.stat().st_mode & 0o777)
            self.assertEqual(0o600, result.public_key_path.stat().st_mode & 0o777)

    def test_existing_or_relative_export_root_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with self.assertRaisesRegex(ValueError, "new absolute"):
                export_network_authority(
                    root, identity_root=root / "identity",
                    display_name="owner device", owner_uid=os.geteuid(),
                )
            with self.assertRaisesRegex(ValueError, "new absolute"):
                export_network_authority(
                    Path("relative"), identity_root=root / "identity",
                    display_name="owner device", owner_uid=os.geteuid(),
                )


if __name__ == "__main__":
    unittest.main()
