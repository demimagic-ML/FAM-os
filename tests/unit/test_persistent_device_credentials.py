import json
import os
import stat
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from cryptography import x509

from fam_os.fabric.credentials import (
    DEVICE_CREDENTIAL_CONTRACT_VERSION,
    DeviceIdentityRecoveryRequired,
    PersistentDeviceIdentityStore,
)

NOW = datetime(2026, 7, 17, 12, tzinfo=UTC)


class PersistentDeviceCredentialTests(unittest.TestCase):
    def test_identity_and_tls_chain_survive_restart_without_key_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fabric/identity"
            first = self._store(root).resolve("Test workstation")
            first_private = first.paths.identity_key.read_bytes()
            second = self._store(root).resolve("Test workstation")

            self.assertEqual(first.identity, second.identity)
            self.assertEqual(first_private, second.paths.identity_key.read_bytes())
            self.assertEqual(DEVICE_CREDENTIAL_CONTRACT_VERSION, second.contract_version)
            self.assertEqual(first.identity.device_id, _certificate_device(second.tls_certificate))
            for path in (
                second.paths.metadata, second.paths.identity_key,
                second.paths.identity_certificate, second.paths.tls_key,
                second.paths.tls_chain,
            ):
                self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
                self.assertEqual(os.geteuid(), path.stat().st_uid)
            self.assertEqual(0o700, stat.S_IMODE(root.stat().st_mode))

    def test_incomplete_identity_fails_closed_without_silent_regeneration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "identity"
            root.mkdir(mode=0o700)
            marker = root / "identity-key.pem"
            marker.write_bytes(b"partial-secret")
            marker.chmod(0o600)
            with self.assertRaisesRegex(DeviceIdentityRecoveryRequired, "incomplete"):
                self._store(root).resolve("Test workstation")
            self.assertEqual(b"partial-secret", marker.read_bytes())

    def test_metadata_or_display_name_tampering_does_not_replace_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "identity"
            credentials = self._store(root).resolve("Test workstation")
            original_key = credentials.paths.identity_key.read_bytes()
            document = json.loads(credentials.paths.metadata.read_text("utf-8"))
            document["device_id"] = "device-" + "0" * 24
            credentials.paths.metadata.write_text(json.dumps(document), encoding="utf-8")
            credentials.paths.metadata.chmod(0o600)

            with self.assertRaisesRegex(DeviceIdentityRecoveryRequired, "corrupt"):
                self._store(root).resolve("Test workstation")
            self.assertEqual(original_key, credentials.paths.identity_key.read_bytes())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "identity"
            credentials = self._store(root).resolve("Original name")
            with self.assertRaisesRegex(DeviceIdentityRecoveryRequired, "corrupt"):
                self._store(root).resolve("Changed name")
            self.assertEqual("Original name", credentials.identity.display_name)

    def _store(self, root: Path) -> PersistentDeviceIdentityStore:
        return PersistentDeviceIdentityStore(root, os.geteuid(), now=lambda: NOW)


def _certificate_device(certificate: x509.Certificate) -> str:
    values = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    return values.get_values_for_type(x509.UniformResourceIdentifier)[0].removeprefix(
        "urn:fam-os:",
    )


if __name__ == "__main__":
    unittest.main()
