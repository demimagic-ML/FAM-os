import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from fam_os.adapters.linux.network_namespace import (
    LinuxNamespaceNetworkEnforcementAdapter,
)
from fam_os.supervisor import NetworkAttachmentKind, NetworkEnforcementSpec
from fam_os.supervisor.network_proxy import ProxyUsage
from tests.contract.schema_integration_environment_fixtures import NOW


class Result:
    def __init__(self, succeeded=True):
        self.succeeded, self.stderr = succeeded, "deliberate failure"


class Client:
    ip, nft = "/usr/sbin/ip", "/usr/sbin/nft"
    def __init__(self, fail_at=None): self.calls, self.fail_at = [], fail_at
    def run(self, command):
        self.calls.append(tuple(str(item) for item in command))
        return Result(len(self.calls) != self.fail_at)


class Proxy:
    def __init__(self, usage=None):
        self.calls, self.observer = [], None
        self.usage = usage or ProxyUsage((), 0, 0, False)
    def start(self, identity, host, destinations, maximum, expires_at, observer):
        self.calls.append(("start", identity, host, destinations, maximum))
        self.observer = observer; observer(self.usage); return 8080
    def snapshot(self, identity): self.calls.append(("snapshot", identity)); return self.usage
    def stop(self, identity): self.calls.append(("stop", identity)); return self.usage
    def recover(self, identity, fallback):
        self.calls.append(("recover", identity)); return self.usage if self.usage.destinations else fallback


class LinuxNamespaceNetworkEnforcementTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "state"
        self.spec = NetworkEnforcementSpec(
            "fam-network-environment-1", "environment-1",
            (NetworkAttachmentKind.LINUX_NAMESPACE,), ("registry.example:443",),
            10_000, NOW + timedelta(minutes=5), "a" * 64,
        )

    def _adapter(self, client=None, proxy=None):
        return LinuxNamespaceNetworkEnforcementAdapter(
            self.root, proxy or Proxy(), client or Client(), lambda: NOW,
        )

    def test_namespace_proxy_and_nft_policy_are_applied_then_closed(self):
        client, proxy = Client(), Proxy(ProxyUsage(("registry.example:443",), 10, 20, False))
        adapter = self._adapter(client, proxy)
        lease = adapter.open(self.spec)
        attachment = lease.attachments[0]
        self.assertEqual(NetworkAttachmentKind.LINUX_NAMESPACE, attachment.kind)
        self.assertTrue(attachment.attachment_reference.startswith("/run/netns/fam-net-"))
        self.assertTrue(attachment.proxy_uri.startswith("http://[fd42:"))
        rendered = tuple(" ".join(item) for item in client.calls)
        self.assertTrue(any("netns add" in item for item in rendered))
        self.assertTrue(any("policy drop" in item and "output" in item for item in rendered))
        self.assertTrue(any("ip6 daddr" in item and "dport 8080" in item for item in rendered))
        live = adapter.observe(self.spec.enforcement_id)
        self.assertFalse(live.finalized)
        closed = adapter.close(self.spec.enforcement_id)
        self.assertTrue(closed.finalized)
        self.assertEqual(30, closed.transmitted_bytes + closed.received_bytes)
        self.assertIn(("stop", self.spec.enforcement_id), proxy.calls)
        self.assertTrue(any("netns delete" in item for item in (" ".join(x) for x in client.calls)))

    def test_quota_exhaustion_observation_forces_terminal_cleanup(self):
        usage = ProxyUsage(("registry.example:443",), 6_000, 4_000, True)
        proxy = Proxy(usage); adapter = self._adapter(proxy=proxy)
        adapter.open(self.spec)
        result = adapter.observe(self.spec.enforcement_id)
        self.assertTrue(result.finalized)
        self.assertTrue(result.quota_exceeded)
        self.assertIn(("stop", self.spec.enforcement_id), proxy.calls)

    def test_partial_setup_failure_recovers_proxy_and_namespace(self):
        client, proxy = Client(fail_at=10), Proxy()
        with self.assertRaisesRegex(RuntimeError, "network policy setup"):
            self._adapter(client, proxy).open(self.spec)
        self.assertIn(("recover", self.spec.enforcement_id), proxy.calls)
        self.assertTrue(any(call[:3] == (client.ip, "netns", "delete") for call in client.calls))

    def test_restart_recovery_uses_durable_usage_and_deterministic_identity(self):
        first_proxy = Proxy(ProxyUsage(("registry.example:443",), 10, 20, False))
        self._adapter(proxy=first_proxy).open(self.spec)
        client, restarted_proxy = Client(), Proxy()
        result = self._adapter(client, restarted_proxy).recover(self.spec)
        self.assertTrue(result.finalized)
        self.assertEqual(30, result.transmitted_bytes + result.received_bytes)
        self.assertTrue(any(call[:3] == (client.ip, "netns", "delete") for call in client.calls))

    def test_other_attachment_kind_fails_before_state_or_command(self):
        client = Client()
        with self.assertRaisesRegex(PermissionError, "namespace"):
            self._adapter(client).open(
                NetworkEnforcementSpec(
                    self.spec.enforcement_id, self.spec.environment_id,
                    (NetworkAttachmentKind.DOCKER_INTERNAL_NETWORK,),
                    self.spec.destinations, self.spec.maximum_network_bytes,
                    self.spec.expires_at, self.spec.request_digest,
                ),
            )
        self.assertEqual([], client.calls)


if __name__ == "__main__":
    unittest.main()
