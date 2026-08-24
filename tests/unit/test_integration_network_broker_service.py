import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.integration.network_broker_service import (
    NetworkBrokerServiceConfiguration, compose_network_broker_service,
)


class IntegrationNetworkBrokerServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve(); self.root.chmod(0o700)
        self.socket_root = self.root / "socket"
        self.broker_state = self.root / "broker-state"
        self.linux_state = self.root / "linux-state"
        self.audit_root = self.root / "audit"
        for path in (
            self.socket_root, self.broker_state, self.linux_state, self.audit_root,
        ):
            path.mkdir(mode=0o700)
        key = Ed25519PrivateKey.generate().public_key()
        self.key_path = self.root / "network-authority.pem"
        self.key_path.write_bytes(key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        self.key_path.chmod(0o600)
        cgroup = next(
            line[3:] for line in Path("/proc/self/cgroup").read_text().splitlines()
            if line.startswith("0::")
        )
        self.configuration = NetworkBrokerServiceConfiguration(
            self.socket_root / "broker.sock", os.geteuid(), os.getegid(),
            os.geteuid(), cgroup, self.broker_state, self.linux_state,
            self.audit_root / "supervisor.jsonl", "device-key-1", self.key_path,
        )

    def test_composed_service_opens_private_socket_and_stops(self):
        service = compose_network_broker_service(self.configuration)
        thread = threading.Thread(target=service.run); thread.start()
        for _ in range(100):
            if self.configuration.socket_path.exists(): break
            time.sleep(0.01)
        self.assertTrue(self.configuration.socket_path.is_socket())
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
            stream.connect(str(self.configuration.socket_path))
            stream.sendall(b"invalid\n"); stream.shutdown(socket.SHUT_WR)
        service.stop(); thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertFalse(self.configuration.socket_path.exists())

    def test_mutable_trust_key_and_broad_state_root_are_rejected(self):
        self.key_path.chmod(0o666)
        with self.assertRaisesRegex(PermissionError, "trust key"):
            compose_network_broker_service(self.configuration)
        self.key_path.chmod(0o600); self.broker_state.chmod(0o770)
        with self.assertRaisesRegex(PermissionError, "directory"):
            compose_network_broker_service(self.configuration)


if __name__ == "__main__":
    unittest.main()
