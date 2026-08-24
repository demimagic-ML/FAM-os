"""Production composition of the private local Application Fabric."""

from dataclasses import dataclass

from fam_os.applications import ApplicationCapabilityRegistry
from fam_os.applications.transport import (
    ConnectorRequestBroker,
    PeerAuthorizationPolicy,
    UnixApplicationServer,
    UnixEndpointConfiguration,
)


@dataclass(frozen=True, slots=True)
class ApplicationFabric:
    registry: ApplicationCapabilityRegistry
    broker: ConnectorRequestBroker
    server: UnixApplicationServer

    @classmethod
    def compose(cls, socket_path, owner_uid: int) -> "ApplicationFabric":
        registry = ApplicationCapabilityRegistry()
        broker = ConnectorRequestBroker(registry)
        server = UnixApplicationServer(
            UnixEndpointConfiguration(socket_path),
            PeerAuthorizationPolicy(owner_uid),
            broker,
        )
        return cls(registry, broker, server)

    def open(self) -> None:
        self.server.open()

    def serve_once(self) -> None:
        self.server.serve_once()

    def close(self) -> None:
        self.server.close()
        self.broker.close()
