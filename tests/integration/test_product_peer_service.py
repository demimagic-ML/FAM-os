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
    PeerControlResponse,
    PeerControlStatus,
    PeerEndpoint,
    PersistentDeviceIdentityStore,
    confirm_pairing,
    create_pairing_offer,
    pairing_code,
)
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.composition.peer_service import ProductPeerService, ProductPeerSettings
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.schemas import dumps_document, loads_document

NOW = datetime(2026, 7, 17, 12, tzinfo=UTC)


class ProductPeerServiceTests(unittest.TestCase):
    def test_persisted_pairing_starts_listener_and_identity_survives_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            port = _unused_port()
            database, repository = _repository(root)
            server, desktop, server_approval, desktop_approval = _approvals(root, port)
            repository.enroll(server_approval)
            service = ProductPeerService(
                ProductPeerSettings(root, "Server", "127.0.0.1", port),
                repository, os.geteuid(),
            )
            first = service.start()
            self.assertEqual("listening", first.state)
            self.assertEqual(server.identity.device_id, first.device_id)
            self.assertEqual(1, first.active_peer_count)

            trust = PairedPeerTrust(
                desktop, (desktop_approval,), str(os.geteuid()),
                now=lambda: NOW + timedelta(seconds=2),
            )
            request = PeerControlRequest(
                "health-1", desktop.identity.device_id,
                PeerControlOperation.HEALTH, NOW + timedelta(seconds=2),
            )
            _, payload = MutualTlsPeerClient(trust).request(
                server.identity.device_id, dumps_document(request).encode(),
            )
            response = loads_document(payload.decode())
            self.assertIsInstance(response, PeerControlResponse)
            self.assertEqual(PeerControlStatus.READY, response.status)
            self.assertEqual(server.identity.device_id, response.responder_device_id)
            service.stop()

            restarted = ProductPeerService(
                ProductPeerSettings(root, "Server", "127.0.0.1", port),
                repository, os.geteuid(),
            )
            second = restarted.start()
            self.assertEqual(first.device_id, second.device_id)
            self.assertEqual("listening", second.state)
            restarted.stop()
            database.close()

    def test_no_enrollment_creates_identity_without_exposing_listener(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database, repository = _repository(root)
            service = ProductPeerService(
                ProductPeerSettings(root, "Unpaired", "127.0.0.1", _unused_port()),
                repository, os.geteuid(),
            )
            status = service.start()
            self.assertEqual("awaiting_pairing", status.state)
            self.assertEqual(0, status.active_peer_count)
            self.assertIsNone(status.listen_port)
            self.assertTrue((root / "fabric/identity/identity-key.pem").is_file())
            service.stop()
            database.close()


def _repository(root):
    database = ProductionDatabase(StorageSettings(root / "state/fam.sqlite3", os.geteuid()))
    opened = SecureStorage(
        database, OwnerKeyStore(root / "state/master.key", os.geteuid()),
    ).open()
    repository = CoreStorageComposition(
        database, opened.cipher, str(os.geteuid()),
    ).repositories().peer_enrollments
    return database, repository


def _approvals(root, port):
    server = PersistentDeviceIdentityStore(
        root / "fabric/identity", os.geteuid(), now=lambda: NOW,
    ).resolve("Server")
    desktop = PersistentDeviceIdentityStore(
        root / "desktop", os.geteuid(), now=lambda: NOW,
    ).resolve("Desktop")
    server_offer = create_pairing_offer(
        server, PeerEndpoint("127.0.0.1", port),
        created_at=NOW, request_id="server-offer",
    )
    desktop_offer = create_pairing_offer(
        desktop, PeerEndpoint("127.0.0.1", max(1, port - 1)),
        created_at=NOW, request_id="desktop-offer",
    )
    code = pairing_code(server_offer, desktop_offer)
    approved = NOW + timedelta(seconds=1)
    server_approval = confirm_pairing(
        server, server_offer, desktop_offer, code,
        owner_id=str(os.geteuid()), approved_at=approved,
    )
    desktop_approval = confirm_pairing(
        desktop, desktop_offer, server_offer, code,
        owner_id=str(os.geteuid()), approved_at=approved,
    )
    return server, desktop, server_approval, desktop_approval


def _unused_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


if __name__ == "__main__":
    unittest.main()
