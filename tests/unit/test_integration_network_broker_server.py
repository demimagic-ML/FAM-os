import os
import base64
import socket
import tempfile
import threading
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from fam_os.adapters.integration import (
    UnixIntegrationNetworkBroker, UnixIntegrationNetworkBrokerServer,
)
from fam_os.core.engineering import (
    IntegrationNetworkAttachmentKind, IntegrationNetworkEnforcementRequest,
    IntegrationNetworkAttachment, IntegrationNetworkLease,
    IntegrationNetworkUsage,
)
from fam_os.schemas import dumps_document
from tests.contract.schema_integration_environment_fixtures import NOW


class Handler:
    def __init__(self, request): self.request, self.calls = request, []
    def open(self, request): self.calls.append("open"); return self._lease()
    def observe(self, lease): self.calls.append("observe"); return self._usage(False)
    def close(self, lease): self.calls.append("close"); return self._usage(True)
    def recover(self, request): self.calls.append("recover"); return self._usage(True)
    def _lease(self):
        value = self.request
        return IntegrationNetworkLease(
            "fam-network-test", value.request_id, value.environment_id,
            value.principal_id, value.session_id, value.authority_ref,
            (IntegrationNetworkAttachment(
                value.attachment_kinds[0], "/run/netns/fam-network-test",
                "http://10.0.0.1:8080",
            ),), value.destinations,
            value.maximum_network_bytes, NOW, value.expires_at, "b" * 64,
        )
    def _usage(self, finalized):
        return IntegrationNetworkUsage(
            "fam-network-test", self.request.environment_id,
            self.request.destinations, 10, 20,
            self.request.maximum_network_bytes, False, finalized, NOW, "c" * 64,
        )


class IntegrationNetworkBrokerServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name).resolve(); root.chmod(0o700)
        self.path = root / "network.sock"
        self.request = IntegrationNetworkEnforcementRequest(
            "network-request-1", "environment-1", "permit-1", "host-1",
            "fam-core", "session-1", "authority-network-1", "device-key-1",
            base64.b64encode(b"\0" * 64).decode(), "a" * 64,
            (IntegrationNetworkAttachmentKind.LINUX_NAMESPACE,),
            ("registry.example:443",), 10_000, NOW + timedelta(minutes=5),
        )
        self.handler = Handler(self.request)
        self.cgroup = next(
            line[3:] for line in Path("/proc/self/cgroup").read_text().splitlines()
            if line.startswith("0::")
        )
        self.server = UnixIntegrationNetworkBrokerServer(
            self.path, socket_owner_uid=os.geteuid(), socket_group_id=os.getegid(),
            allowed_peer_uid=os.geteuid(), allowed_peer_cgroup=self.cgroup,
            handler=self.handler,
        )
        self.server.open(); self.addCleanup(self.server.close)

    def _serve(self):
        failures = []
        def run():
            try: self.server.serve_once()
            except Exception as error: failures.append(error)
        thread = threading.Thread(target=run); thread.start()
        return thread, failures

    def test_real_peer_authenticated_round_trip_for_all_operations(self):
        client = UnixIntegrationNetworkBroker(self.path)
        results = []
        thread, failures = self._serve(); lease = client.open(self.request); thread.join(2); results += failures
        thread, failures = self._serve(); client.observe(lease); thread.join(2); results += failures
        thread, failures = self._serve(); client.close(lease); thread.join(2); results += failures
        thread, failures = self._serve(); client.recover(self.request); thread.join(2); results += failures
        self.assertEqual([], results)
        self.assertEqual(["open", "observe", "close", "recover"], self.handler.calls)
        self.assertEqual(0o660, self.path.stat().st_mode & 0o777)

    def test_wrong_peer_uid_is_closed_without_dispatch(self):
        thread, failures = self._serve()
        with patch(
            "fam_os.adapters.integration.network_broker_server._peer_allowed",
            return_value=False,
        ):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
                stream.connect(str(self.path)); stream.sendall(b"invalid\n")
                stream.shutdown(socket.SHUT_WR)
                try:
                    response = stream.recv(10)
                except ConnectionResetError:
                    response = b""
                self.assertEqual(b"", response)
        thread.join(2)
        self.assertEqual([], failures)
        self.assertEqual([], self.handler.calls)

    def test_same_uid_from_wrong_cgroup_is_closed_without_dispatch(self):
        self.server.close()
        self.server = UnixIntegrationNetworkBrokerServer(
            self.path, socket_owner_uid=os.geteuid(), socket_group_id=os.getegid(),
            allowed_peer_uid=os.geteuid(),
            allowed_peer_cgroup="/deliberately-different-fam-core.scope",
            handler=self.handler,
        )
        self.server.open(); self.addCleanup(self.server.close)
        thread, failures = self._serve()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
            stream.connect(str(self.path)); stream.sendall(b"invalid\n")
            stream.shutdown(socket.SHUT_WR)
            try: response = stream.recv(10)
            except ConnectionResetError: response = b""
        thread.join(2)
        self.assertEqual(b"", response)
        self.assertEqual([], failures)
        self.assertEqual([], self.handler.calls)

    def test_oversized_request_fails_before_dispatch(self):
        self.server.close()
        self.server = UnixIntegrationNetworkBrokerServer(
            self.path, socket_owner_uid=os.geteuid(), socket_group_id=os.getegid(),
            allowed_peer_uid=os.geteuid(), allowed_peer_cgroup=self.cgroup,
            handler=self.handler,
            maximum_message_bytes=64,
        )
        self.server.open(); self.addCleanup(self.server.close)
        thread, failures = self._serve()
        request = ("open\n" + dumps_document(self.request) + "\n").encode()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
            stream.connect(str(self.path)); stream.sendall(request)
            stream.shutdown(socket.SHUT_WR)
        thread.join(2)
        self.assertIsInstance(failures[0], ValueError)
        self.assertEqual([], self.handler.calls)


if __name__ == "__main__":
    unittest.main()
