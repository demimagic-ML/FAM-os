import socket
import threading
import unittest

from fam_os.supervisor.network_proxy import (
    BoundedConnectProxySession, NetworkByteQuota,
)


def resolver(address="93.184.216.34"):
    return lambda *_args, **_kwargs: (
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)),
    )


class SupervisorNetworkProxyTests(unittest.TestCase):
    def _session(self, maximum=100, *, address="93.184.216.34"):
        observed = []
        quota = NetworkByteQuota(maximum, observed.append)
        proxy_remote, server = socket.socketpair()
        self.addCleanup(proxy_remote.close); self.addCleanup(server.close)
        session = BoundedConnectProxySession(
            ("registry.example:443",), quota, resolver=resolver(address),
            dialer=lambda *_args, **_kwargs: proxy_remote,
        )
        return session, quota, observed, server

    def _start(self, session):
        client, proxy = socket.socketpair(); self.addCleanup(client.close)
        failures = []
        def run():
            try: session.serve(proxy)
            except Exception as error: failures.append(error)
            finally: proxy.close()
        thread = threading.Thread(target=run); thread.start()
        return client, thread, failures

    def test_exact_global_destination_relays_and_accounts_both_directions(self):
        session, quota, observed, server = self._session()
        client, thread, failures = self._start(session)
        client.sendall(b"CONNECT registry.example:443 HTTP/1.1\r\nHost: registry.example:443\r\n\r\n")
        self.assertIn(b"200 Connection Established", client.recv(1024))
        client.sendall(b"abc")
        self.assertEqual(b"abc", server.recv(3))
        server.sendall(b"xyz")
        self.assertEqual(b"xyz", client.recv(3))
        client.shutdown(socket.SHUT_RDWR); thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual([], failures)
        usage = quota.snapshot()
        self.assertEqual(("registry.example:443",), usage.destinations)
        self.assertEqual((3, 3, False), (
            usage.transmitted_bytes, usage.received_bytes, usage.quota_exceeded,
        ))
        self.assertTrue(observed)

    def test_unapproved_destination_is_denied_before_resolution_or_dial(self):
        session, quota, _observed, _server = self._session()
        client, thread, failures = self._start(session)
        client.sendall(b"CONNECT metadata.example:443 HTTP/1.1\r\n\r\n")
        self.assertIn(b"403 Forbidden", client.recv(1024))
        thread.join(2)
        self.assertIsInstance(failures[0], PermissionError)
        self.assertEqual((), quota.snapshot().destinations)

    def test_domain_resolution_to_private_address_fails_closed(self):
        session, quota, _observed, _server = self._session(address="127.0.0.1")
        client, thread, failures = self._start(session)
        client.sendall(b"CONNECT registry.example:443 HTTP/1.1\r\n\r\n")
        self.assertIn(b"502 Bad Gateway", client.recv(1024))
        thread.join(2)
        self.assertIsInstance(failures[0], OSError)
        self.assertEqual(0, quota.snapshot().received_bytes)

    def test_quota_is_consumed_before_forwarding_and_closes_at_limit(self):
        session, quota, _observed, server = self._session(maximum=5)
        client, thread, failures = self._start(session)
        client.sendall(b"CONNECT registry.example:443 HTTP/1.1\r\n\r\n")
        client.recv(1024)
        client.sendall(b"abc")
        self.assertEqual(b"abc", server.recv(3))
        server.sendall(b"wxyz")
        self.assertEqual(b"wx", client.recv(4))
        thread.join(2)
        usage = quota.snapshot()
        self.assertEqual(5, usage.transmitted_bytes + usage.received_bytes)
        self.assertTrue(usage.quota_exceeded)
        self.assertEqual([], failures)

    def test_exact_quota_fill_closes_without_marking_permitted_bytes_exceeded(self):
        session, quota, _observed, server = self._session(maximum=3)
        client, thread, failures = self._start(session)
        client.sendall(b"CONNECT registry.example:443 HTTP/1.1\r\n\r\n")
        client.recv(1024); client.sendall(b"abc")
        self.assertEqual(b"abc", server.recv(3))
        thread.join(2)
        self.assertFalse(thread.is_alive())
        usage = quota.snapshot()
        self.assertEqual(3, usage.transmitted_bytes)
        self.assertFalse(usage.quota_exceeded)
        self.assertEqual([], failures)

    def test_proxy_authorization_header_is_forbidden(self):
        session, _quota, _observed, _server = self._session()
        client, thread, failures = self._start(session)
        client.sendall(
            b"CONNECT registry.example:443 HTTP/1.1\r\n"
            b"Proxy-Authorization: secret\r\n\r\n"
        )
        thread.join(2)
        self.assertIsInstance(failures[0], ValueError)


if __name__ == "__main__":
    unittest.main()
