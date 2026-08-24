import socket
import unittest
from datetime import timedelta

from fam_os.supervisor.network_proxy_runtime import ThreadedConnectProxyRuntime
from tests.contract.schema_integration_environment_fixtures import NOW


class Clock:
    def __init__(self): self.value = NOW
    def __call__(self): return self.value


class SupervisorNetworkProxyRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.proxy_remote, self.remote = socket.socketpair()
        self.addCleanup(self.proxy_remote.close); self.addCleanup(self.remote.close)
        resolver = lambda *_args, **_kwargs: (
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        )
        self.runtime = ThreadedConnectProxyRuntime(
            clock=self.clock, resolver=resolver,
            dialer=lambda *_args, **_kwargs: self.proxy_remote,
        )

    def test_real_listener_relays_accounts_and_stops(self):
        observed = []
        port = self.runtime.start(
            "fam-network-test", "::1", ("registry.example:443",), 100,
            NOW + timedelta(minutes=1), observed.append,
        )
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as client:
            client.connect(("::1", port))
            client.sendall(b"CONNECT registry.example:443 HTTP/1.1\r\n\r\n")
            self.assertIn(b"200 Connection Established", client.recv(1024))
            client.sendall(b"abc"); self.assertEqual(b"abc", self.remote.recv(3))
            self.remote.sendall(b"xyz"); self.assertEqual(b"xyz", client.recv(3))
        usage = self.runtime.stop("fam-network-test")
        self.assertEqual((3, 3), (usage.transmitted_bytes, usage.received_bytes))
        self.assertTrue(observed)

    def test_expiry_marks_runtime_inactive_until_owner_finalizes_it(self):
        self.runtime.start(
            "fam-network-expiry", "::1", ("registry.example:443",), 100,
            NOW + timedelta(seconds=1), lambda _usage: None,
        )
        self.clock.value = NOW + timedelta(seconds=1)
        usage = self.runtime.snapshot("fam-network-expiry")
        self.assertEqual(0, usage.transmitted_bytes)
        self.assertFalse(self.runtime.active("fam-network-expiry"))
        self.runtime.stop("fam-network-expiry")
        with self.assertRaises(FileNotFoundError):
            self.runtime.snapshot("fam-network-expiry")

    def test_duplicate_and_missing_identities_fail_closed(self):
        self.runtime.start(
            "fam-network-duplicate", "::1", ("registry.example:443",), 100,
            NOW + timedelta(minutes=1), lambda _usage: None,
        )
        with self.assertRaises(FileExistsError):
            self.runtime.start(
                "fam-network-duplicate", "::1", ("registry.example:443",), 100,
                NOW + timedelta(minutes=1), lambda _usage: None,
            )
        self.runtime.stop("fam-network-duplicate")
        with self.assertRaises(FileNotFoundError):
            self.runtime.stop("fam-network-duplicate")

    def test_multiple_listeners_share_one_aggregate_quota(self):
        pairs = [socket.socketpair(), socket.socketpair()]
        for pair in pairs:
            self.addCleanup(pair[0].close); self.addCleanup(pair[1].close)
        available = iter(pair[0] for pair in pairs)
        runtime = ThreadedConnectProxyRuntime(
            clock=self.clock,
            resolver=lambda *_args, **_kwargs: (
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            ),
            dialer=lambda *_args, **_kwargs: next(available),
        )
        addresses = runtime.start_many(
            "fam-network-shared", ("127.0.0.1", "::1"),
            ("registry.example:443",), 9, NOW + timedelta(minutes=1),
            lambda _usage: None,
        )
        self.assertEqual(2, len(addresses))
        families = (socket.AF_INET, socket.AF_INET6)
        clients = []
        for index, (family, (host, port)) in enumerate(zip(families, addresses)):
            client = socket.socket(family, socket.SOCK_STREAM); clients.append(client)
            self.addCleanup(client.close)
            client.connect((host, port))
            client.sendall(b"CONNECT registry.example:443 HTTP/1.1\r\n\r\n")
            self.assertIn(b"200 Connection Established", client.recv(1024))
            client.sendall(b"abc")
            self.assertEqual(b"abc", pairs[index][1].recv(3))
        pairs[0][1].sendall(b"xyz")
        self.assertEqual(b"xyz", clients[0].recv(3))
        usage = runtime.stop("fam-network-shared")
        self.assertEqual(9, usage.transmitted_bytes + usage.received_bytes)


if __name__ == "__main__":
    unittest.main()
