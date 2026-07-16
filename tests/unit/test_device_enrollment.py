import base64
import hashlib
import unittest
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.fabric.identity import (
    DeviceEnrollmentAuthority, DeviceEnrollmentChallenge, DeviceEnrollmentRequest,
    DeviceIdentity, _challenge_bytes,
)

NOW = datetime(2026, 7, 16, tzinfo=UTC)


class DeviceEnrollmentTests(unittest.TestCase):
    def test_proof_of_private_key_enrolls_exact_owner(self):
        private = Ed25519PrivateKey.generate()
        raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        identity = DeviceIdentity("desktop", "Desktop", base64.b64encode(raw).decode(), hashlib.sha256(raw).hexdigest())
        request = DeviceEnrollmentRequest("request", identity, NOW)
        challenge = DeviceEnrollmentChallenge("request", base64.b64encode(b"nonce" * 8).decode(), NOW + timedelta(minutes=1))
        signature = base64.b64encode(private.sign(_challenge_bytes(challenge))).decode()
        record = DeviceEnrollmentAuthority().enroll(request, challenge, signature, "owner", NOW)
        self.assertTrue(record.trusted)
        self.assertEqual("owner", record.owner_id)

    def test_expired_challenge_is_rejected(self):
        challenge = DeviceEnrollmentChallenge("request", "bm9uY2U=", NOW)
        with self.assertRaisesRegex(ValueError, "expired"):
            DeviceEnrollmentAuthority().enroll(None, challenge, "", "owner", NOW)


if __name__ == "__main__":
    unittest.main()
