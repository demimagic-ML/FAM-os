"""Composition and bounded run loop for the external network broker daemon."""

from dataclasses import dataclass
from pathlib import Path
import socket
from threading import Event

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.adapters.audit import JsonlHashChainAuditSink
from fam_os.adapters.crypto import Ed25519IntegrationNetworkAuthority
from fam_os.adapters.integration.network_authorizer import (
    VerifiedNetworkSupervisorAuthorizer,
)
from fam_os.adapters.integration.network_broker_handler import (
    IntegrationNetworkBrokerHandler,
)
from fam_os.adapters.integration.network_broker_server import (
    UnixIntegrationNetworkBrokerServer,
)
from fam_os.adapters.integration.network_broker_state import NetworkBrokerStateStore
from fam_os.adapters.integration.docker_client import DockerCommandClient
from fam_os.adapters.integration.docker_network_enforcement import (
    DockerInternalNetworkAttachmentResource,
)
from fam_os.adapters.integration.multi_network_enforcement import (
    MultiAttachmentNetworkEnforcementAdapter,
)
from fam_os.adapters.linux.network_namespace import (
    LinuxNamespaceAttachmentResource, LinuxNetworkCommandClient,
)
from fam_os.supervisor import (
    AuditedNetworkEnforcementController, NetworkEnforcementController,
    NetworkAttachmentKind, SupervisorAuditEmitter,
)
from fam_os.supervisor.network_proxy_runtime import ThreadedConnectProxyRuntime


@dataclass(frozen=True, slots=True)
class NetworkBrokerServiceConfiguration:
    socket_path: Path
    socket_owner_uid: int
    socket_group_id: int
    allowed_core_uid: int
    allowed_core_cgroup: str
    broker_state_root: Path
    linux_state_root: Path
    audit_path: Path
    trusted_key_id: str
    trusted_public_key_path: Path

    def __post_init__(self):
        paths = (
            self.socket_path, self.broker_state_root, self.linux_state_root,
            self.audit_path, self.trusted_public_key_path,
        )
        if any(not path.is_absolute() for path in paths):
            raise ValueError("network broker paths must be absolute")
        if min(self.socket_owner_uid, self.socket_group_id, self.allowed_core_uid) < 0:
            raise ValueError("network broker identities must be nonnegative")
        if not self.trusted_key_id.strip() or not self.allowed_core_cgroup.startswith("/"):
            raise ValueError("network broker trust configuration is invalid")


class NetworkBrokerService:
    def __init__(self, server):
        self._server, self._stop = server, Event()

    def run(self):
        self._server.open()
        try:
            while not self._stop.is_set():
                try: self._server.serve_once()
                except socket.timeout: continue
                except (EOFError, OSError, PermissionError, TypeError, ValueError):
                    continue
        finally:
            self._server.close()

    def stop(self):
        self._stop.set()


def compose_network_broker_service(configuration):
    _secure_directory(
        configuration.socket_path.parent, configuration.socket_owner_uid,
        allow_group_traverse=True,
    )
    for path in (
        configuration.broker_state_root, configuration.linux_state_root,
        configuration.audit_path.parent,
    ):
        _secure_directory(path, configuration.socket_owner_uid)
    public_key = _public_key(
        configuration.trusted_public_key_path, configuration.socket_owner_uid,
    )
    verifier = Ed25519IntegrationNetworkAuthority({
        configuration.trusted_key_id: public_key,
    })
    authorities = VerifiedNetworkSupervisorAuthorizer()
    linux_client = LinuxNetworkCommandClient()
    resources = {
        NetworkAttachmentKind.LINUX_NAMESPACE:
            LinuxNamespaceAttachmentResource(linux_client),
    }
    try:
        docker_client = DockerCommandClient()
    except (OSError, PermissionError):
        pass
    else:
        resources[NetworkAttachmentKind.DOCKER_INTERNAL_NETWORK] = (
            DockerInternalNetworkAttachmentResource(docker_client, linux_client)
        )
    adapter = MultiAttachmentNetworkEnforcementAdapter(
        configuration.linux_state_root, ThreadedConnectProxyRuntime(), resources,
    )
    controller = AuditedNetworkEnforcementController(
        NetworkEnforcementController(authorities, adapter),
        SupervisorAuditEmitter(JsonlHashChainAuditSink(configuration.audit_path)),
    )
    handler = IntegrationNetworkBrokerHandler(
        controller, NetworkBrokerStateStore(configuration.broker_state_root),
        controller.audit.clock, verifier, authorities,
    )
    server = UnixIntegrationNetworkBrokerServer(
        configuration.socket_path,
        socket_owner_uid=configuration.socket_owner_uid,
        socket_group_id=configuration.socket_group_id,
        allowed_peer_uid=configuration.allowed_core_uid,
        allowed_peer_cgroup=configuration.allowed_core_cgroup,
        handler=handler,
    )
    return NetworkBrokerService(server)


def _public_key(path, owner_uid):
    details = path.stat(follow_symlinks=False)
    if (
        path.is_symlink() or not path.is_file() or details.st_uid != owner_uid
        or details.st_mode & 0o022
    ):
        raise PermissionError("network broker trust key is mutable or invalid")
    value = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(value, Ed25519PublicKey):
        raise TypeError("network broker trust key must be Ed25519")
    return value


def _secure_directory(path, owner_uid, *, allow_group_traverse=False):
    details = path.stat(follow_symlinks=False)
    if (
        path.is_symlink() or not path.is_dir() or details.st_uid != owner_uid
        or details.st_mode & (0o027 if allow_group_traverse else 0o077)
    ):
        raise PermissionError("network broker directory ownership is invalid")
