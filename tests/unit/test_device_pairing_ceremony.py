import base64
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.fabric.credentials import PersistentDeviceIdentityStore
from fam_os.fabric.pairing import (
    PeerEndpoint,
    confirm_pairing,
    create_pairing_offer,
    pairing_code,
    pairing_offer_document,
    verify_pairing_approval,
    verify_pairing_offer,
)
from fam_os.fabric import PeerEnrollmentRecord, PeerEnrollmentState
from tools.phase21_physical_exit.assemble_pairing import pairing_document

NOW = datetime(2026, 7, 17, 12, tzinfo=UTC)


class DevicePairingCeremonyTests(unittest.TestCase):
    def test_two_signed_offers_produce_same_owner_confirmed_code_and_approvals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            desktop = self._credentials(root / "desktop", "Desktop")
            server = self._credentials(root / "server", "Home server")
            desktop_offer = create_pairing_offer(
                desktop, PeerEndpoint("192.0.2.10", 48121),
                created_at=NOW, request_id="pair-desktop",
            )
            server_offer = create_pairing_offer(
                server, PeerEndpoint("192.0.2.20", 48121),
                created_at=NOW, request_id="pair-server",
            )

            code = pairing_code(desktop_offer, server_offer)
            self.assertEqual(code, pairing_code(server_offer, desktop_offer))
            self.assertRegex(code, r"^\d{4}-\d{4}-\d{4}$")
            desktop_approval = confirm_pairing(
                desktop, desktop_offer, server_offer, code,
                owner_id="uid:1000", approved_at=NOW + timedelta(seconds=1),
            )
            server_approval = confirm_pairing(
                server, server_offer, desktop_offer, code,
                owner_id="uid:1000", approved_at=NOW + timedelta(seconds=1),
            )

            verify_pairing_approval(desktop_approval, desktop.identity)
            verify_pairing_approval(server_approval, server.identity)
            self.assertEqual(server.identity, desktop_approval.peer_identity)
            self.assertEqual(desktop.identity, server_approval.peer_identity)
            self.assertEqual(desktop_approval.ceremony_sha256, server_approval.ceremony_sha256)
            self.assertNotIn(code, str(pairing_offer_document(desktop_offer)))

            evidence = pairing_document(
                PeerEnrollmentRecord(
                    "enrollment-desktop", desktop_approval,
                    PeerEnrollmentState.ACTIVE, 1, NOW + timedelta(seconds=1),
                ),
                PeerEnrollmentRecord(
                    "enrollment-server", server_approval,
                    PeerEnrollmentState.ACTIVE, 1, NOW + timedelta(seconds=1),
                ),
            )
            self.assertEqual(desktop.identity.device_id, evidence["requester_device_id"])
            self.assertEqual(server.identity.device_id, evidence["peer_device_id"])
            self.assertTrue(evidence["pairing_codes_match"])

    def test_wrong_code_expiry_tampering_and_certificate_substitution_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            desktop = self._credentials(root / "desktop", "Desktop")
            server = self._credentials(root / "server", "Server")
            other = self._credentials(root / "other", "Other")
            desktop_offer = create_pairing_offer(
                desktop, PeerEndpoint("desktop.local", 48121),
                created_at=NOW, request_id="desktop",
            )
            server_offer = create_pairing_offer(
                server, PeerEndpoint("server.local", 48121),
                created_at=NOW, request_id="server",
            )
            code = pairing_code(desktop_offer, server_offer)

            with self.assertRaisesRegex(PermissionError, "does not match"):
                confirm_pairing(
                    desktop, desktop_offer, server_offer, "0000-0000-0000",
                    owner_id="uid:1000", approved_at=NOW + timedelta(seconds=1),
                )
            with self.assertRaisesRegex(ValueError, "not currently valid"):
                verify_pairing_offer(server_offer, observed_at=NOW + timedelta(minutes=11))

            broken_signature = replace(
                server_offer,
                signature_base64=base64.b64encode(b"x" * 64).decode("ascii"),
            )
            with self.assertRaisesRegex(ValueError, "trust proof"):
                confirm_pairing(
                    desktop, desktop_offer, broken_signature,
                    pairing_code(desktop_offer, broken_signature),
                    owner_id="uid:1000", approved_at=NOW + timedelta(seconds=1),
                )

            substituted = replace(
                server_offer,
                identity_certificate_base64=other.identity_certificate_base64,
            )
            with self.assertRaisesRegex(ValueError, "trust proof"):
                verify_pairing_offer(substituted, observed_at=NOW + timedelta(seconds=1))
            self.assertNotEqual(code, pairing_code(desktop_offer, substituted))

    def test_local_offer_must_belong_to_confirming_persistent_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._credentials(root / "first", "First")
            second = self._credentials(root / "second", "Second")
            first_offer = create_pairing_offer(
                first, PeerEndpoint("127.0.0.1", 48121), created_at=NOW,
            )
            second_offer = create_pairing_offer(
                second, PeerEndpoint("127.0.0.1", 48122), created_at=NOW,
            )
            with self.assertRaisesRegex(ValueError, "does not belong"):
                confirm_pairing(
                    second, first_offer, second_offer,
                    pairing_code(first_offer, second_offer),
                    owner_id="uid:1000", approved_at=NOW + timedelta(seconds=1),
                )

    @staticmethod
    def _credentials(root: Path, name: str):
        return PersistentDeviceIdentityStore(
            root, os.geteuid(), now=lambda: NOW,
        ).resolve(name)


if __name__ == "__main__":
    unittest.main()
