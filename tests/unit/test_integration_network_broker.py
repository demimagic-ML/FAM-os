import unittest
import base64
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from fam_os.adapters.integration import UnixIntegrationNetworkBroker
from fam_os.core.engineering import (
    IntegrationNetworkAttachmentKind,
    IntegrationNetworkAttachment,
    IntegrationNetworkEnforcementRequest,
    IntegrationNetworkLease,
    IntegrationNetworkUsage,
)
from fam_os.schemas import dumps_document
from tests.contract.schema_integration_environment_fixtures import NOW


class FakeSocket:
    def __init__(self, response):
        self.response = bytearray(response)
        self.sent = bytearray()

    def __enter__(self): return self
    def __exit__(self, *_args): return None
    def settimeout(self, value): self.timeout = value
    def connect(self, path): self.path = path
    def sendall(self, value): self.sent.extend(value)
    def shutdown(self, _how): pass
    def recv(self, size):
        value = bytes(self.response[:size]); del self.response[:size]
        return value


class SocketFactory:
    def __init__(self, documents):
        self.responses = [(dumps_document(item) + "\n").encode() for item in documents]
        self.sockets = []

    def __call__(self, *_args):
        value = FakeSocket(self.responses.pop(0)); self.sockets.append(value)
        return value


class IntegrationNetworkBrokerTests(unittest.TestCase):
    def setUp(self):
        self.request = IntegrationNetworkEnforcementRequest(
            "network-request-1", "environment-1", "permit-1", "host-1",
            "fam-core", "session-1", "authority-network-1", "device-key-1",
            base64.b64encode(b"\0" * 64).decode(), "a" * 64,
            (IntegrationNetworkAttachmentKind.LINUX_NAMESPACE,),
            ("registry.example:443",), 10_000, NOW + timedelta(minutes=5),
        )
        self.lease = IntegrationNetworkLease(
            "enforcement-1", self.request.request_id,
            self.request.environment_id, self.request.principal_id,
            self.request.session_id, self.request.authority_ref,
            (IntegrationNetworkAttachment(
                self.request.attachment_kinds[0],
                "/run/netns/fam-environment-1", "http://10.0.0.1:8080",
            ),),
            self.request.destinations, self.request.maximum_network_bytes,
            NOW, self.request.expires_at, "b" * 64,
        )
        self.live = IntegrationNetworkUsage(
            self.lease.enforcement_id, self.request.environment_id,
            self.request.destinations, 100, 200,
            self.request.maximum_network_bytes, False, False, NOW, "c" * 64,
        )
        self.final = IntegrationNetworkUsage(
            self.lease.enforcement_id, self.request.environment_id,
            self.request.destinations, 100, 200,
            self.request.maximum_network_bytes, False, True, NOW, "d" * 64,
        )

    def test_strict_bounded_open_observe_close_and_recover(self):
        factory = SocketFactory((self.lease, self.live, self.final, self.final))
        with patch(
            "fam_os.adapters.integration.network_broker.socket.socket", factory,
        ):
            broker = UnixIntegrationNetworkBroker(Path("/run/fam/network.sock"))
            self.assertEqual(self.lease, broker.open(self.request))
            self.assertEqual(self.live, broker.observe(self.lease))
            self.assertEqual(self.final, broker.close(self.lease))
            self.assertEqual(self.final, broker.recover(self.request))
        self.assertTrue(factory.sockets[0].sent.startswith(b"open\n"))
        self.assertTrue(factory.sockets[1].sent.startswith(b"observe\n"))
        self.assertTrue(factory.sockets[2].sent.startswith(b"close\n"))
        self.assertTrue(factory.sockets[3].sent.startswith(b"recover\n"))
        self.assertTrue(all(item.path == "/run/fam/network.sock" for item in factory.sockets))

    def test_substituted_lease_and_unfinalized_close_fail(self):
        bad_lease = IntegrationNetworkLease(
            self.lease.enforcement_id, self.lease.request_id,
            self.lease.environment_id, self.lease.principal_id,
            self.lease.session_id, self.lease.authority_ref,
            self.lease.attachments,
            self.lease.destinations, self.lease.maximum_network_bytes + 1,
            self.lease.issued_at, self.lease.expires_at, self.lease.evidence_sha256,
        )
        factory = SocketFactory((bad_lease, self.live))
        with patch(
            "fam_os.adapters.integration.network_broker.socket.socket", factory,
        ):
            broker = UnixIntegrationNetworkBroker(Path("/run/fam/network.sock"))
            with self.assertRaisesRegex(ValueError, "differs"):
                broker.open(self.request)
            with self.assertRaisesRegex(ValueError, "did not finalize"):
                broker.close(self.lease)

    def test_transport_bounds_are_enforced(self):
        factory = SocketFactory((self.lease,))
        with patch(
            "fam_os.adapters.integration.network_broker.socket.socket", factory,
        ):
            broker = UnixIntegrationNetworkBroker(
                Path("/run/fam/network.sock"), maximum_message_bytes=32,
            )
            with self.assertRaisesRegex(ValueError, "request exceeds"):
                broker.open(self.request)


if __name__ == "__main__":
    unittest.main()
