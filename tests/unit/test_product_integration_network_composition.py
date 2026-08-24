import base64
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.core.engineering.integration_network import (
    IntegrationNetworkAttachmentKind,
    IntegrationNetworkEnforcementRequest,
)
from fam_os.product.composition.integration_network import (
    compose_integration_network_client,
)
from tests.contract.schema_integration_environment_fixtures import NOW


class ProductIntegrationNetworkCompositionTests(unittest.TestCase):
    def test_network_authority_is_absent_until_owner_selects_socket(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertIsNone(compose_integration_network_client(
                None, identity_root=root / "identity",
                display_name="owner device", owner_uid=os.geteuid(),
            ))
            self.assertFalse((root / "identity").exists())

    def test_selected_socket_uses_persistent_device_identity_to_sign(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            credentials = SimpleNamespace(
                identity=SimpleNamespace(device_id="device-persistent-1"),
                identity_key=Ed25519PrivateKey.generate(),
            )
            with patch(
                "fam_os.product.composition.integration_network."
                "PersistentDeviceIdentityStore"
            ) as store:
                store.return_value.resolve.return_value = credentials
                client = compose_integration_network_client(
                    root / "broker.sock", identity_root=root / "identity",
                    display_name="owner device", owner_uid=os.geteuid(),
                )
                request = IntegrationNetworkEnforcementRequest(
                    request_id="request-1", environment_id="environment-1",
                    permit_id="permit-1", exact_host_id="host-1",
                    principal_id="owner", session_id="session-1",
                    authority_ref="authority-1", signer_key_id=client.signer_key_id,
                    signature_base64=base64.b64encode(b"\0" * 64).decode(),
                    plan_sha256="a" * 64,
                    destinations=("example.com:443",), maximum_network_bytes=4096,
                    expires_at=NOW + timedelta(minutes=5),
                    attachment_kinds=(
                        IntegrationNetworkAttachmentKind.LINUX_NAMESPACE,
                    ),
                )
                signed = client.authority.sign(request)
                self.assertNotEqual(request.signature_base64, signed.signature_base64)
                self.assertEqual(client.signer_key_id, signed.signer_key_id)
                restarted = compose_integration_network_client(
                    root / "broker.sock", identity_root=root / "identity",
                    display_name="owner device", owner_uid=os.geteuid(),
                )
            self.assertEqual(client.signer_key_id, restarted.signer_key_id)

    def test_relative_socket_is_rejected_before_identity_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                compose_integration_network_client(
                    Path("broker.sock"), identity_root=root / "identity",
                    display_name="owner device", owner_uid=os.geteuid(),
                )
            self.assertFalse((root / "identity").exists())


if __name__ == "__main__":
    unittest.main()
