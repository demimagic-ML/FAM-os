"""Linux namespace and nftables enforcement for process integration egress."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from fam_os.adapters.linux.bounded_command import BoundedSubprocessRunner
from fam_os.adapters.linux.integration_network_state import (
    LinuxIntegrationNetworkState,
)
from fam_os.supervisor.network_contracts import (
    NetworkAttachment, NetworkAttachmentKind, NetworkEnforcementLease,
    NetworkUsageSnapshot,
)
from fam_os.supervisor.network_proxy import ProxyUsage


class LinuxNetworkCommandClient:
    def __init__(
        self, ip: Path = Path("/usr/sbin/ip"),
        nft: Path = Path("/usr/sbin/nft"), runner=None,
    ) -> None:
        resolved = []
        for path in (ip, nft):
            link = path.lstat()
            target = path.resolve(strict=True)
            details = target.stat(follow_symlinks=False)
            if link.st_uid != 0 or not target.is_file() or details.st_uid != 0:
                raise PermissionError("network enforcement tool is not root-owned")
            if details.st_mode & 0o022 or not os.access(path, os.X_OK):
                raise PermissionError("network enforcement tool is mutable or not executable")
            resolved.append(target)
        self.ip, self.nft = resolved
        self._runner = runner or BoundedSubprocessRunner()

    def run(self, arguments):
        command = tuple(str(item) for item in arguments)
        return self._runner.run(command, environment={"LANG": "C", "LC_ALL": "C"})


class LinuxNamespaceNetworkEnforcementAdapter:
    def __init__(self, state_root: Path, proxy_runtime, client=None, clock=None):
        self._root = state_root
        self._proxy = proxy_runtime
        self._resource = LinuxNamespaceAttachmentResource(
            client or LinuxNetworkCommandClient(),
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def open(self, spec):
        if spec.attachment_kinds != (NetworkAttachmentKind.LINUX_NAMESPACE,):
            raise PermissionError("Linux adapter accepts only namespace attachments")
        state = LinuxIntegrationNetworkState(self._root, spec.enforcement_id)
        state.claim(spec)
        resource = self._resource.for_identity(spec.enforcement_id)
        try:
            resource = self._resource.create(spec)
            state.stage("namespace")
            port = self._proxy.start(
                spec.enforcement_id, resource.bind_host, spec.destinations,
                spec.maximum_network_bytes, spec.expires_at, state.record_usage,
            )
            state.stage("proxy", proxy_port=port)
            self._resource.activate(resource, port)
            state.stage("ready")
        except BaseException as open_error:
            errors = []
            try: self._proxy.recover(spec.enforcement_id, _state_usage(state))
            except BaseException as error: errors.append(error)
            try: self._resource.remove(resource)
            except BaseException as error: errors.append(error)
            if errors:
                raise RuntimeError("namespace network compensation is incomplete") from errors[-1]
            state.stage("recovered")
            raise open_error
        issued = self._clock()
        evidence = _digest(spec, resource.names, port)
        return NetworkEnforcementLease(
            spec.enforcement_id, (self._resource.attachment(resource, port),),
            spec.destinations, spec.maximum_network_bytes,
            issued, spec.expires_at, evidence,
        )

    def observe(self, enforcement_id):
        state = LinuxIntegrationNetworkState(self._root, enforcement_id)
        if hasattr(self._proxy, "active") and not self._proxy.active(enforcement_id):
            return self.close(enforcement_id)
        usage = self._proxy.snapshot(enforcement_id)
        state.record_usage(usage)
        if usage.quota_exceeded:
            return self.close(enforcement_id)
        return _snapshot(enforcement_id, state.load(), False, self._clock())

    def close(self, enforcement_id):
        state = LinuxIntegrationNetworkState(self._root, enforcement_id)
        usage, errors = None, []
        try:
            usage = self._proxy.stop(enforcement_id); state.record_usage(usage)
        except BaseException as error: errors.append(error)
        try: self._resource.remove(self._resource.for_identity(enforcement_id))
        except BaseException as error: errors.append(error)
        if errors:
            raise RuntimeError("namespace network cleanup is incomplete") from errors[-1]
        state.stage("closed")
        return _snapshot(enforcement_id, state.load(), True, self._clock())

    def recover(self, spec):
        state = LinuxIntegrationNetworkState(self._root, spec.enforcement_id)
        try:
            document = state.load()
        except FileNotFoundError:
            usage = ProxyUsage((), 0, 0, False)
            document = None
        else:
            if document["request_digest"] != spec.request_digest:
                raise PermissionError("Linux network recovery request is mismatched")
            usage = _state_usage(state)
        errors = []
        try: usage = self._proxy.recover(spec.enforcement_id, usage)
        except BaseException as error: errors.append(error)
        try: self._resource.remove(self._resource.for_identity(spec.enforcement_id))
        except BaseException as error: errors.append(error)
        if errors:
            raise RuntimeError("namespace network recovery is incomplete") from errors[-1]
        if document is not None:
            state.record_usage(usage); state.stage("recovered")
            document = state.load()
        else:
            document = _usage_document(spec, usage)
        return _snapshot(spec.enforcement_id, document, True, self._clock())

class LinuxNamespaceAttachmentResource:
    def __init__(self, client):
        self._client = client

    def for_identity(self, identity):
        return _LinuxNamespaceResource(_network_identity(identity))

    def create(self, spec):
        resource = self.for_identity(spec.enforcement_id)
        namespace, host_veth, guest_veth, host_ip, guest_ip = resource.names
        commands = (
            (self._client.ip, "netns", "add", namespace),
            (self._client.ip, "link", "add", host_veth, "type", "veth", "peer", "name", guest_veth),
            (self._client.ip, "link", "set", guest_veth, "netns", namespace),
            (self._client.ip, "-6", "addr", "add", host_ip + "/126", "dev", host_veth),
            (self._client.ip, "link", "set", host_veth, "up"),
            (self._client.ip, "-n", namespace, "-6", "addr", "add", guest_ip + "/126", "dev", guest_veth),
            (self._client.ip, "-n", namespace, "link", "set", "lo", "up"),
            (self._client.ip, "-n", namespace, "link", "set", guest_veth, "up"),
        )
        for command in commands:
            _required(self._client.run(command), "network namespace setup")
        return resource

    def activate(self, resource, port):
        namespace, _host_veth, _guest_veth, host_ip, _guest_ip = resource.names
        prefix = (self._client.ip, "netns", "exec", namespace, self._client.nft)
        commands = (
            ("add", "table", "inet", "fam"),
            ("add", "chain", "inet", "fam", "output", "{ type filter hook output priority 0 ; policy drop ; }"),
            ("add", "rule", "inet", "fam", "output", "oifname", "lo", "accept"),
            ("add", "rule", "inet", "fam", "output", "ip6", "daddr", host_ip, "tcp", "dport", str(port), "accept"),
            ("add", "chain", "inet", "fam", "input", "{ type filter hook input priority 0 ; policy drop ; }"),
            ("add", "rule", "inet", "fam", "input", "iifname", "lo", "accept"),
            ("add", "rule", "inet", "fam", "input", "ct", "state", "established,related", "accept"),
        )
        for command in commands:
            _required(self._client.run(prefix + command), "network policy setup")

    def attachment(self, resource, port):
        namespace, _host_veth, _guest_veth, host_ip, _guest_ip = resource.names
        return NetworkAttachment(
            NetworkAttachmentKind.LINUX_NAMESPACE,
            "/run/netns/" + namespace, f"http://[{host_ip}]:{port}",
        )

    def remove(self, resource):
        namespace, host_veth = resource.names[:2]
        self._client.run((self._client.ip, "netns", "delete", namespace))
        self._client.run((self._client.ip, "link", "delete", host_veth))


class _LinuxNamespaceResource:
    def __init__(self, names): self.names = names

    @property
    def bind_host(self): return self.names[3]


def _network_identity(identity):
    digest = hashlib.sha256(identity.encode()).hexdigest()
    namespace = "fam-net-" + digest[:12]
    host_veth, guest_veth = "fh" + digest[:11], "fg" + digest[:11]
    groups = ":".join(digest[index:index + 4] for index in range(12, 28, 4))
    return namespace, host_veth, guest_veth, f"fd42:{groups}::1", f"fd42:{groups}::2"


def _required(result, operation):
    if not result.succeeded:
        raise RuntimeError(operation + " failed: " + result.stderr[-1024:])


def _state_usage(state):
    document = state.load()
    return ProxyUsage(
        tuple(document["observed_destinations"]),
        document["transmitted_bytes"], document["received_bytes"],
        document["quota_exceeded"],
    )


def _snapshot(identity, document, finalized, instant):
    evidence = hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()
    return NetworkUsageSnapshot(
        identity, tuple(document["observed_destinations"]),
        document["transmitted_bytes"], document["received_bytes"],
        document["maximum_network_bytes"], document["quota_exceeded"],
        finalized, instant, evidence,
    )


def _usage_document(spec, usage):
    return {
        "observed_destinations": list(usage.destinations),
        "transmitted_bytes": usage.transmitted_bytes,
        "received_bytes": usage.received_bytes,
        "maximum_network_bytes": spec.maximum_network_bytes,
        "quota_exceeded": usage.quota_exceeded,
    }


def _digest(spec, names, port):
    value = (spec.request_digest, *names, str(port))
    return hashlib.sha256("\0".join(value).encode()).hexdigest()
