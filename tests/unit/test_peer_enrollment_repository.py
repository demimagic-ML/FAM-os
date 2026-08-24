import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.fabric import (
    PeerEndpoint,
    PeerEnrollmentState,
    PersistentDeviceIdentityStore,
    confirm_pairing,
    create_pairing_offer,
    pairing_code,
)
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.product.storage.peer_enrollment_repository import SqlitePeerEnrollmentRepository

NOW = datetime(2026, 7, 17, 12, tzinfo=UTC)


class PeerEnrollmentRepositoryTests(unittest.TestCase):
    def test_pairing_approval_is_encrypted_restart_safe_and_revocable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            approval = _approval(root)
            database, repository, _ = _repository(root)
            enrolled = repository.enroll(approval)
            self.assertEqual((enrolled,), repository.active())
            raw = database.fetchone(
                "SELECT payload_ciphertext FROM fabric_peer_enrollments WHERE enrollment_id=?",
                (enrolled.enrollment_id,),
            )[0]
            self.assertNotIn(approval.peer_identity.device_id, raw)
            self.assertNotIn(approval.peer_identity.display_name, raw)
            database.close()

            database, repository, _ = _repository(root)
            self.assertEqual(enrolled, repository.get(enrolled.enrollment_id))
            self.assertEqual(enrolled, repository.enroll(approval))
            revoked = repository.revoke(
                enrolled.enrollment_id, expected_revision=1,
                revoked_at=NOW + timedelta(minutes=2), reason_code="owner.revoked",
            )
            self.assertEqual(PeerEnrollmentState.REVOKED, revoked.state)
            self.assertEqual(2, revoked.revision)
            self.assertEqual((), repository.active())
            self.assertEqual(revoked, repository.get(enrolled.enrollment_id))
            database.close()

    def test_owner_and_revision_mismatch_fail_without_changing_active_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            approval = _approval(root)
            database, repository, cipher = _repository(root)
            enrolled = repository.enroll(approval)
            with self.assertRaisesRegex(RuntimeError, "revision changed"):
                repository.revoke(
                    enrolled.enrollment_id, expected_revision=7,
                    revoked_at=NOW + timedelta(minutes=2), reason_code="owner.revoked",
                )
            self.assertEqual((enrolled,), repository.active())

            other = SqlitePeerEnrollmentRepository(database, cipher, "another-owner")
            with self.assertRaisesRegex(PermissionError, "another owner"):
                other.enroll(approval)
            database.close()


def _repository(root):
    database = ProductionDatabase(StorageSettings(root / "state/fam.sqlite3", os.geteuid()))
    opened = SecureStorage(
        database, OwnerKeyStore(root / "state/master.key", os.geteuid()),
    ).open()
    repository = CoreStorageComposition(
        database, opened.cipher, "uid:test-owner",
    ).repositories().peer_enrollments
    return database, repository, opened.cipher


def _approval(root):
    desktop = PersistentDeviceIdentityStore(
        root / "desktop", os.geteuid(), now=lambda: NOW,
    ).resolve("Desktop")
    server = PersistentDeviceIdentityStore(
        root / "server", os.geteuid(), now=lambda: NOW,
    ).resolve("Server")
    desktop_offer = create_pairing_offer(
        desktop, PeerEndpoint("127.0.0.1", 48121),
        created_at=NOW, request_id="desktop-offer",
    )
    server_offer = create_pairing_offer(
        server, PeerEndpoint("127.0.0.1", 48122),
        created_at=NOW, request_id="server-offer",
    )
    return confirm_pairing(
        desktop, desktop_offer, server_offer, pairing_code(desktop_offer, server_offer),
        owner_id="uid:test-owner", approved_at=NOW + timedelta(seconds=1),
    )


if __name__ == "__main__":
    unittest.main()
