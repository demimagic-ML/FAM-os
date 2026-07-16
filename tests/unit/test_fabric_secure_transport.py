import base64
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from fam_os.fabric.transport import FabricSecureChannel, create_handshake


def public(key):
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


class FabricSecureTransportTests(unittest.TestCase):
    def test_signed_handshake_derives_bidirectional_authenticated_channel(self):
        a_sign, b_sign = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
        a_eph, b_eph = X25519PrivateKey.generate(), X25519PrivateKey.generate()
        a = FabricSecureChannel.establish("session", a_eph, create_handshake("b", b_sign, b_eph), public(b_sign))
        b = FabricSecureChannel.establish("session", b_eph, create_handshake("a", a_sign, a_eph), public(a_sign))
        envelope = a.encrypt(1, b"private context")
        self.assertEqual(b"private context", b.decrypt(envelope))
        with self.assertRaisesRegex(ValueError, "replay"):
            b.decrypt(envelope)


if __name__ == "__main__":
    unittest.main()
