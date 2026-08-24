import os
import socket
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.fabric import (
    MutualTlsPeerClient,
    PairedPeerTrust,
    PeerControlOperation,
    PeerControlRequest,
    PeerEndpoint,
    PeerManagementOperation,
    PeerManagementRequest,
    PersistentDeviceIdentityStore,
    RemoteContextSensitivity,
    RemotePrivacyPolicy,
    confirm_pairing,
    create_capability_declaration,
    create_pairing_offer,
    pairing_code,
)
from fam_os.product.composition.peer_service import ProductPeerService, ProductPeerSettings
from fam_os.product.composition.storage_unit import ProductStorageUnit
from fam_os.product.peer_management import ProductPeerManagement
from fam_os.schemas import dumps_document

NOW = datetime(2026, 7, 17, 12, tzinfo=UTC)


class ProductPeerManagementTests(unittest.TestCase):
    def test_probe_privacy_and_live_revocation_are_durable_and_trusted_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            server_root, desktop_root = root / "server", root / "desktop"
            port = _unused_port()
            server_creds, desktop_creds, server_approval, desktop_approval = _approvals(
                server_root, desktop_root, port,
            )
            server_storage, server_repositories = _storage(server_root)
            desktop_storage, desktop_repositories = _storage(desktop_root)
            server_repositories.peer_enrollments.enroll(server_approval)
            desktop_record = desktop_repositories.peer_enrollments.enroll(desktop_approval)
            server = ProductPeerService(
                ProductPeerSettings(server_root, "Server", "127.0.0.1", port),
                server_repositories.peer_enrollments, os.geteuid(), _capabilities,
            )
            desktop = ProductPeerService(
                ProductPeerSettings(desktop_root, "Desktop"),
                desktop_repositories.peer_enrollments, os.geteuid(),
            )
            try:
                server.start()
                desktop.start()
                desktop_management = ProductPeerManagement(
                    desktop_repositories.peer_enrollments,
                    desktop_repositories.peer_state, desktop, str(os.geteuid()),
                )
                probed = desktop_management.probe(desktop_record.enrollment_id, "probe-1")
                self.assertEqual(("test:q4",), tuple(item.model_ref for item in probed.capabilities))
                self.assertIsNotNone(probed.latest_performance)
                self.assertGreaterEqual(probed.latest_performance.round_trip_milliseconds, 0)
                self.assertIsNone(probed.privacy)
                refreshed = desktop_management.probe(
                    desktop_record.enrollment_id, "probe-2",
                )
                self.assertEqual(2, len(
                    desktop_repositories.peer_state.performance(desktop_record.enrollment_id),
                ))
                self.assertEqual(("test:q4",), tuple(
                    item.model_ref for item in refreshed.capabilities
                ))

                policy = RemotePrivacyPolicy(
                    str(os.geteuid()), (server_creds.identity.device_id,),
                    ("assist",), ("workspace:test",), 4096,
                    (RemoteContextSensitivity.PRIVATE,), False,
                )
                privacy = PeerManagementRequest(
                    "privacy-1", str(os.geteuid()), PeerManagementOperation.SET_PRIVACY,
                    desktop_record.enrollment_id, 0, True, "owner.configured", policy,
                )
                receipt = desktop_management.apply_control(privacy)
                self.assertTrue(receipt.applied)
                self.assertEqual(receipt, desktop_management.apply_control(privacy))
                self.assertEqual(1, desktop_management.peer(desktop_record.enrollment_id).privacy.revision)
                database = desktop_storage.result.database
                self.assertIsNotNone(database)
                raw = database.fetchone(
                    "SELECT payload_ciphertext FROM fabric_peer_privacy_policies "
                    "WHERE enrollment_id=?", (desktop_record.enrollment_id,),
                )[0]
                self.assertNotIn("workspace:test", raw)
                self.assertNotIn("test:q4", "".join(
                    str(row[0]) for row in database.fetchall(
                        "SELECT payload_ciphertext FROM fabric_peer_capabilities",
                    )
                ))

                server_record = server_repositories.peer_enrollments.active()[0]
                server_management = ProductPeerManagement(
                    server_repositories.peer_enrollments, server_repositories.peer_state,
                    server, str(os.geteuid()),
                )
                with self.assertRaisesRegex(PermissionError, "confirmation"):
                    server_management.apply_control(PeerManagementRequest(
                        "revoke-denied", str(os.geteuid()), PeerManagementOperation.REVOKE,
                        server_record.enrollment_id, 1, False, "owner.revoked",
                    ))
                old_trust = PairedPeerTrust(
                    desktop_creds, (desktop_approval,), str(os.geteuid()),
                )
                revoked = server_management.apply_control(PeerManagementRequest(
                    "revoke-1", str(os.geteuid()), PeerManagementOperation.REVOKE,
                    server_record.enrollment_id, 1, True, "owner.revoked",
                ))
                self.assertTrue(revoked.applied)
                self.assertEqual("awaiting_pairing", server.status().state)
                self.assertEqual((), server_management.trusted_peers())
                with self.assertRaises(OSError):
                    MutualTlsPeerClient(old_trust).request(
                        server_creds.identity.device_id,
                        dumps_document(PeerControlRequest(
                            "health-after-revoke", desktop_creds.identity.device_id,
                            PeerControlOperation.HEALTH, datetime.now(UTC),
                        )).encode(),
                    )
            finally:
                desktop.stop()
                server.stop()
                desktop_storage.stop()
                server_storage.stop()


def _storage(root):
    storage = ProductStorageUnit(root, os.geteuid())
    opened = storage.start()
    if opened.recovery_required or storage.core is None:
        raise RuntimeError("test storage did not open")
    return storage, storage.core.repositories()


def _approvals(server_root, desktop_root, port):
    server = PersistentDeviceIdentityStore(
        server_root / "fabric/identity", os.geteuid(), now=lambda: NOW,
    ).resolve("Server")
    desktop = PersistentDeviceIdentityStore(
        desktop_root / "fabric/identity", os.geteuid(), now=lambda: NOW,
    ).resolve("Desktop")
    server_offer = create_pairing_offer(
        server, PeerEndpoint("127.0.0.1", port), created_at=NOW,
        request_id="server-offer",
    )
    desktop_offer = create_pairing_offer(
        desktop, PeerEndpoint("127.0.0.1", _unused_port()), created_at=NOW,
        request_id="desktop-offer",
    )
    code = pairing_code(server_offer, desktop_offer)
    approved = NOW + timedelta(seconds=1)
    return (
        server, desktop,
        confirm_pairing(
            server, server_offer, desktop_offer, code,
            owner_id=str(os.geteuid()), approved_at=approved,
        ),
        confirm_pairing(
            desktop, desktop_offer, server_offer, code,
            owner_id=str(os.geteuid()), approved_at=approved,
        ),
    )


def _capabilities(credentials, observed_at):
    revision = max(1, int(observed_at.timestamp() * 1_000_000))
    return (create_capability_declaration(
        credentials, declaration_id=f"capability-{revision}",
        expert_tier="economical",
        expert_id="expert.code", model_ref="test:q4",
        capability_ids=("code.generate",), maximum_context_bytes=8192,
        manifest_sha256="a" * 64, revision=revision, issued_at=observed_at,
        expires_at=observed_at + timedelta(hours=1),
    ),)


def _unused_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


if __name__ == "__main__":
    unittest.main()
