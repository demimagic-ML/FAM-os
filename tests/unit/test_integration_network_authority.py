import base64
import unittest
from dataclasses import replace
from datetime import timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.crypto import Ed25519IntegrationNetworkAuthority
from fam_os.core.engineering import (
    IntegrationNetworkAttachmentKind, IntegrationNetworkEnforcementRequest,
)
from tests.contract.schema_integration_environment_fixtures import NOW


class IntegrationNetworkAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        self.draft = IntegrationNetworkEnforcementRequest(
            "request-1", "environment-1", "permit-1", "host-1", "fam-core",
            "session-1", "authority-1", "device-key-1",
            base64.b64encode(b"\0" * 64).decode(), "a" * 64,
            (IntegrationNetworkAttachmentKind.LINUX_NAMESPACE,),
            ("registry.example:443",), 10_000, NOW + timedelta(minutes=5),
        )

    def test_exact_request_is_signed_and_verified(self):
        authority = Ed25519IntegrationNetworkAuthority(
            {"device-key-1": self.key.public_key()},
            signing_key_id="device-key-1", signing_key=self.key,
        )
        request = authority.sign(self.draft)
        authority.verify(request)
        self.assertNotEqual(self.draft.signature_base64, request.signature_base64)
        with self.assertRaisesRegex(PermissionError, "signature"):
            authority.verify(replace(request, maximum_network_bytes=10_001))

    def test_unknown_signer_and_signer_substitution_fail(self):
        verifier = Ed25519IntegrationNetworkAuthority({})
        with self.assertRaisesRegex(PermissionError, "not trusted"):
            verifier.verify(self.draft)
        signer = Ed25519IntegrationNetworkAuthority(
            {}, signing_key_id="other-key", signing_key=self.key,
        )
        with self.assertRaisesRegex(PermissionError, "mismatched"):
            signer.sign(self.draft)


if __name__ == "__main__":
    unittest.main()
