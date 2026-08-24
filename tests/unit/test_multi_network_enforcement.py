import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from fam_os.adapters.integration.multi_network_enforcement import (
    MultiAttachmentNetworkEnforcementAdapter,
)
from fam_os.supervisor import (
    NetworkAttachment, NetworkAttachmentKind, NetworkEnforcementSpec,
)
from fam_os.supervisor.network_proxy import ProxyUsage
from tests.contract.schema_integration_environment_fixtures import NOW


class Resource:
    def __init__(self, kind, host): self.kind, self.host, self.calls = kind, host, []
    def for_identity(self, identity): return SimpleNamespace(identity=identity, bind_host=self.host)
    def create(self, spec): self.calls.append(("create", spec.enforcement_id)); return self.for_identity(spec.enforcement_id)
    def activate(self, resource, port): self.calls.append(("activate", port))
    def attachment(self, resource, port):
        return NetworkAttachment(self.kind, self.kind.value + "-ref", f"http://[{self.host}]:{port}")
    def remove(self, resource): self.calls.append(("remove", resource.identity))


class Proxy:
    def __init__(self):
        self.calls, self.usage = [], ProxyUsage(("registry.example:443",), 3, 4, False)
    def start_many(self, identity, hosts, destinations, maximum, expires, observer):
        self.calls.append(("start", identity, hosts, maximum)); observer(self.usage)
        return tuple((host, 8000 + index) for index, host in enumerate(hosts))
    def snapshot(self, identity): self.calls.append(("snapshot", identity)); return self.usage
    def stop(self, identity): self.calls.append(("stop", identity)); return self.usage
    def recover(self, identity, fallback): self.calls.append(("recover", identity)); return fallback


class MultiNetworkEnforcementTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.linux = Resource(NetworkAttachmentKind.LINUX_NAMESPACE, "fd42::1")
        self.docker = Resource(NetworkAttachmentKind.DOCKER_INTERNAL_NETWORK, "fd43::1")
        self.proxy = Proxy()
        self.adapter = MultiAttachmentNetworkEnforcementAdapter(
            Path(self.temporary.name).resolve(), self.proxy,
            {self.linux.kind: self.linux, self.docker.kind: self.docker},
            lambda: NOW,
        )
        self.spec = NetworkEnforcementSpec(
            "fam-network-environment-1", "environment-1",
            (self.linux.kind, self.docker.kind), ("registry.example:443",),
            10_000, NOW + timedelta(minutes=5), "a" * 64,
        )

    def test_two_attachments_share_one_proxy_quota_and_terminal_snapshot(self):
        lease = self.adapter.open(self.spec)
        self.assertEqual((self.linux.kind, self.docker.kind), tuple(item.kind for item in lease.attachments))
        self.assertEqual(1, sum(call[0] == "start" for call in self.proxy.calls))
        self.assertEqual(("fd42::1", "fd43::1"), self.proxy.calls[0][2])
        self.assertFalse(self.adapter.observe(self.spec.enforcement_id).finalized)
        usage = self.adapter.close(self.spec.enforcement_id)
        self.assertTrue(usage.finalized); self.assertEqual(7, usage.transmitted_bytes + usage.received_bytes)
        self.assertEqual("remove", self.docker.calls[-1][0])
        self.assertEqual("remove", self.linux.calls[-1][0])

    def test_restart_recovery_removes_every_deterministic_attachment(self):
        self.adapter.open(self.spec)
        restarted = MultiAttachmentNetworkEnforcementAdapter(
            Path(self.temporary.name).resolve(), Proxy(),
            {self.linux.kind: self.linux, self.docker.kind: self.docker},
            lambda: NOW,
        )
        usage = restarted.recover(self.spec)
        self.assertTrue(usage.finalized)
        self.assertEqual("remove", self.linux.calls[-1][0])
        self.assertEqual("remove", self.docker.calls[-1][0])

    def test_root_journal_attachment_tamper_fails_before_cleanup_effect(self):
        self.adapter.open(self.spec)
        path = Path(self.temporary.name) / (self.spec.enforcement_id + ".json")
        value = json.loads(path.read_text())
        value["attachment_kinds"] = ["linux_namespace", "linux_namespace"]
        path.write_text(json.dumps(value))
        before = tuple(self.proxy.calls)
        with self.assertRaisesRegex(ValueError, "attachment state"):
            self.adapter.close(self.spec.enforcement_id)
        self.assertEqual(before, tuple(self.proxy.calls))


if __name__ == "__main__":
    unittest.main()
