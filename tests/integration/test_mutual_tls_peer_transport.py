import os
import socket
import ssl
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.fabric.credentials import PersistentDeviceIdentityStore
from fam_os.fabric.pairing import (
    PeerEndpoint,
    confirm_pairing,
    create_pairing_offer,
    pairing_code,
)
from fam_os.fabric.tls_transport import (
    MutualTlsPeerClient,
    MutualTlsPeerServer,
    PeerTlsServerSettings,
    write_frame,
)
from fam_os.fabric.tls_trust import PairedPeerTrust

NOW = datetime(2026, 7, 17, 12, tzinfo=UTC)
OWNER = "uid:test-owner"


class MutualTlsPeerTransportTests(unittest.TestCase):
    def test_paired_devices_exchange_bounded_payload_over_tls13(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            port = _unused_port()
            desktop, server, desktop_approval, server_approval = _paired(
                root, port, "desktop", "server",
            )
            desktop_trust = _trust(desktop, desktop_approval)
            server_trust = _trust(server, server_approval)
            observed = []
            peer_server = MutualTlsPeerServer(
                PeerTlsServerSettings("127.0.0.1", port), server_trust,
                lambda peer, request: observed.append((peer, request)) or b"peer-ready",
            )
            peer_server.open()
            failures = []
            thread = threading.Thread(target=_serve, args=(peer_server, failures))
            thread.start()
            try:
                peer, response = MutualTlsPeerClient(desktop_trust).request(
                    server.identity.device_id, b"bounded-control-message",
                )
            finally:
                thread.join(timeout=5)
                peer_server.close()

            self.assertFalse(thread.is_alive())
            self.assertEqual([], failures)
            self.assertEqual(b"peer-ready", response)
            self.assertEqual(server.identity.device_id, peer.device_id)
            self.assertEqual("TLSv1.3", peer.tls_version)
            self.assertEqual(desktop.identity.device_id, observed[0][0].device_id)
            self.assertEqual(b"bounded-control-message", observed[0][1])

    def test_unpaired_client_certificate_is_rejected_by_server(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            port = _unused_port()
            desktop, server, _, server_approval = _paired(root, port, "desktop", "server")
            intruder, _, intruder_approval, _ = _paired(
                root, port, "intruder", "server-for-intruder", server_credentials=server,
            )
            server_trust = _trust(server, server_approval)
            intruder_trust = _trust(intruder, intruder_approval)
            peer_server = MutualTlsPeerServer(
                PeerTlsServerSettings("127.0.0.1", port), server_trust,
                lambda _peer, _request: b"must-not-run",
            )
            peer_server.open()
            failures = []
            thread = threading.Thread(target=_serve, args=(peer_server, failures))
            thread.start()
            try:
                with self.assertRaises((ssl.SSLError, ConnectionError)):
                    MutualTlsPeerClient(intruder_trust).request(
                        server.identity.device_id, b"unauthorized",
                    )
            finally:
                thread.join(timeout=5)
                peer_server.close()
            self.assertTrue(failures)
            self.assertIsInstance(failures[0], ssl.SSLError)
            self.assertNotEqual(desktop.identity.device_id, intruder.identity.device_id)

    def test_frame_limit_is_enforced_before_network_write(self):
        left, right = socket.socketpair()
        try:
            with self.assertRaisesRegex(ValueError, "frame size"):
                write_frame(left, b"x" * 1025, 1024)
            right.settimeout(0.02)
            with self.assertRaises(TimeoutError):
                right.recv(1)
        finally:
            left.close()
            right.close()


def _paired(root, port, first_name, second_name, *, server_credentials=None):
    first = _credentials(root / first_name, first_name)
    second = server_credentials or _credentials(root / second_name, second_name)
    first_offer = create_pairing_offer(
        first, PeerEndpoint("127.0.0.1", max(1, port + 1)),
        created_at=NOW, request_id="offer-" + first_name,
    )
    second_offer = create_pairing_offer(
        second, PeerEndpoint("127.0.0.1", port),
        created_at=NOW, request_id="offer-" + second_name,
    )
    code = pairing_code(first_offer, second_offer)
    approved = NOW + timedelta(seconds=1)
    first_approval = confirm_pairing(
        first, first_offer, second_offer, code, owner_id=OWNER, approved_at=approved,
    )
    second_approval = confirm_pairing(
        second, second_offer, first_offer, code, owner_id=OWNER, approved_at=approved,
    )
    return first, second, first_approval, second_approval


def _credentials(root, name):
    return PersistentDeviceIdentityStore(
        root, os.geteuid(), now=lambda: NOW,
    ).resolve(name)


def _trust(credentials, approval):
    return PairedPeerTrust(
        credentials, (approval,), OWNER, now=lambda: NOW + timedelta(seconds=2),
    )


def _unused_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def _serve(server, failures):
    try:
        server.serve_once()
    except BaseException as error:
        failures.append(error)


if __name__ == "__main__":
    unittest.main()
