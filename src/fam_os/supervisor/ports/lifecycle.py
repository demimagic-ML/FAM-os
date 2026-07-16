"""Provider-neutral service lifecycle port."""

from typing import Protocol

from fam_os.supervisor.contracts import ServiceDefinition, ServiceStatus


class ServiceLifecycle(Protocol):
    def start(self, definition: ServiceDefinition) -> ServiceStatus: ...

    def stop(self, service_id: str) -> ServiceStatus: ...

    def status(self, service_id: str) -> ServiceStatus: ...


class ServiceDefinitionProjector(Protocol):
    def project(self, definition: ServiceDefinition) -> ServiceDefinition: ...
