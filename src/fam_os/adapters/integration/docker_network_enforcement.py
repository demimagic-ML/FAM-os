"""Deterministic Docker-internal attachment for broker-owned CONNECT egress."""

from dataclasses import dataclass
import hashlib
import json

from fam_os.adapters.integration.docker_support import required_output
from fam_os.supervisor import NetworkAttachment, NetworkAttachmentKind


@dataclass(frozen=True, slots=True)
class DockerNetworkResource:
    name: str
    bridge_name: str
    subnet: str
    gateway: str
    nft_table: str
    network_id: str | None = None

    @property
    def bind_host(self):
        return self.gateway


class DockerInternalNetworkAttachmentResource:
    def __init__(self, docker_client, linux_client):
        self._docker, self._linux = docker_client, linux_client

    def for_identity(self, identity):
        digest = hashlib.sha256(identity.encode()).hexdigest()
        groups = ":".join(digest[index:index + 4] for index in range(0, 16, 4))
        return DockerNetworkResource(
            "fam-egress-" + digest[:12], "fd" + digest[:12],
            f"fd43:{groups}::/64", f"fd43:{groups}::1",
            "fam_d_" + digest[:12],
        )

    def create(self, spec):
        resource = self.for_identity(spec.enforcement_id)
        result = self._docker.run((
            "network", "create", "--internal", "--ipv4=false", "--ipv6",
            "--subnet", resource.subnet, "--gateway", resource.gateway,
            "--opt", "com.docker.network.bridge.name=" + resource.bridge_name,
            "--label", "fam.environment=" + spec.environment_id,
            "--label", "fam.enforcement=" + spec.enforcement_id,
            resource.name,
        ))
        network_id = required_output(result, "Docker egress network creation")
        created = DockerNetworkResource(
            resource.name, resource.bridge_name, resource.subnet,
            resource.gateway, resource.nft_table, network_id,
        )
        try:
            self._verify(created)
        except BaseException:
            self.remove(created)
            raise
        return created

    def activate(self, resource, port):
        commands = (
            ("add", "table", "inet", resource.nft_table),
            ("add", "chain", "inet", resource.nft_table, "input",
             "{ type filter hook input priority -200 ; policy accept ; }"),
            ("add", "rule", "inet", resource.nft_table, "input",
             "iifname", resource.bridge_name, "ip6", "daddr", resource.gateway,
             "tcp", "dport", str(port), "accept"),
            ("add", "rule", "inet", resource.nft_table, "input",
             "iifname", resource.bridge_name, "drop"),
            ("add", "chain", "inet", resource.nft_table, "forward",
             "{ type filter hook forward priority -200 ; policy accept ; }"),
            ("add", "rule", "inet", resource.nft_table, "forward",
             "iifname", resource.bridge_name, "oifname", resource.bridge_name,
             "accept"),
            ("add", "rule", "inet", resource.nft_table, "forward",
             "iifname", resource.bridge_name, "ct", "state",
             "established,related", "accept"),
            ("add", "rule", "inet", resource.nft_table, "forward",
             "iifname", resource.bridge_name, "drop"),
        )
        for command in commands:
            result = self._linux.run((self._linux.nft, *command))
            if not result.succeeded:
                raise RuntimeError("Docker egress nftables policy setup failed")

    def attachment(self, resource, port):
        if resource.network_id is None:
            raise RuntimeError("Docker egress network identity is unavailable")
        return NetworkAttachment(
            NetworkAttachmentKind.DOCKER_INTERNAL_NETWORK,
            resource.network_id, f"http://[{resource.gateway}]:{port}",
        )

    def remove(self, resource):
        self._linux.run((
            self._linux.nft, "delete", "table", "inet", resource.nft_table,
        ))
        target = resource.network_id or resource.name
        result = self._docker.run(("network", "rm", target))
        if result.exit_code != 0 and not any(
            marker in result.output for marker in (b"not found", b"No such network")
        ):
            raise RuntimeError("Docker egress network cleanup failed")

    def _verify(self, resource):
        result = self._docker.run(("network", "inspect", resource.network_id))
        if result.exit_code != 0:
            raise RuntimeError("Docker egress network inspection failed")
        try:
            values = json.loads(result.output)
            value = values[0]
            configurations = value["IPAM"]["Config"]
            options = value["Options"]
        except (IndexError, KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Docker egress network inspection is invalid") from error
        if (
            len(values) != 1 or value.get("Id") != resource.network_id
            or value.get("Internal") is not True
            or value.get("EnableIPv6") is not True
            or options.get("com.docker.network.bridge.name") != resource.bridge_name
            or configurations != [{
                "Subnet": resource.subnet, "IPRange": "",
                "Gateway": resource.gateway,
            }]
        ):
            raise PermissionError("Docker egress network scope differs from request")
