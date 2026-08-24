import json
import unittest
from types import SimpleNamespace

from fam_os.adapters.integration.docker_client import DockerCommandResult
from fam_os.adapters.integration.docker_network_enforcement import (
    DockerInternalNetworkAttachmentResource,
)
from fam_os.supervisor import NetworkAttachmentKind


class Docker:
    def __init__(self, *, substituted=False):
        self.calls, self.substituted = [], substituted

    def run(self, arguments):
        self.calls.append(arguments)
        if arguments[:2] == ("network", "create"):
            return DockerCommandResult(0, b"network-id-1\n")
        if arguments[:2] == ("network", "inspect"):
            create = self.calls[0]
            subnet = create[create.index("--subnet") + 1]
            gateway = create[create.index("--gateway") + 1]
            bridge = create[create.index("--opt") + 1].split("=", 1)[1]
            value = [{
                "Id": "substituted" if self.substituted else "network-id-1",
                "Internal": True, "EnableIPv6": True,
                "Options": {"com.docker.network.bridge.name": bridge},
                "IPAM": {"Config": [{
                    "Subnet": subnet, "IPRange": "", "Gateway": gateway,
                }]},
            }]
            return DockerCommandResult(0, json.dumps(value).encode())
        return DockerCommandResult(0, b"")


class Linux:
    nft = "/usr/sbin/nft"
    def __init__(self): self.calls = []
    def run(self, arguments):
        self.calls.append(arguments)
        return SimpleNamespace(succeeded=True, stderr="")


class DockerNetworkEnforcementTests(unittest.TestCase):
    def test_internal_ipv6_network_is_verified_filtered_and_removed(self):
        docker, linux = Docker(), Linux()
        provider = DockerInternalNetworkAttachmentResource(docker, linux)
        spec = SimpleNamespace(
            enforcement_id="fam-network-environment-1",
            environment_id="environment-1",
        )
        resource = provider.create(spec)
        provider.activate(resource, 8443)
        attachment = provider.attachment(resource, 8443)
        self.assertEqual(NetworkAttachmentKind.DOCKER_INTERNAL_NETWORK, attachment.kind)
        self.assertEqual("network-id-1", attachment.attachment_reference)
        create = docker.calls[0]
        self.assertIn("--internal", create); self.assertIn("--ipv4=false", create)
        self.assertIn("--ipv6", create)
        rendered = tuple(" ".join(item) for item in linux.calls)
        self.assertTrue(any("iifname" in item and "dport 8443 accept" in item for item in rendered))
        self.assertTrue(any("iifname" in item and "oifname" in item and "accept" in item for item in rendered))
        self.assertTrue(any("established,related accept" in item for item in rendered))
        self.assertTrue(any("forward" in item and "drop" in item for item in rendered))
        provider.remove(resource)
        self.assertIn(("network", "rm", "network-id-1"), docker.calls)

    def test_substituted_network_inspection_is_removed_and_denied(self):
        docker, linux = Docker(substituted=True), Linux()
        provider = DockerInternalNetworkAttachmentResource(docker, linux)
        with self.assertRaisesRegex(PermissionError, "differs"):
            provider.create(SimpleNamespace(
                enforcement_id="fam-network-environment-1",
                environment_id="environment-1",
            ))
        self.assertIn(("network", "rm", "network-id-1"), docker.calls)


if __name__ == "__main__":
    unittest.main()
