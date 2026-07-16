"""User-scoped systemd implementation of the service lifecycle port."""

from dataclasses import dataclass

from fam_os.adapters.linux.command import CommandRunner
from fam_os.adapters.systemd.commands import (
    build_reset_failed_command,
    build_show_command,
    build_start_command,
    build_stop_command,
)
from fam_os.adapters.systemd.parsing import parse_service_status
from fam_os.adapters.systemd.settings import SystemdUserSettings
from fam_os.supervisor import (
    ServiceDefinition,
    ServiceLifecycleError,
    ServiceState,
    ServiceStatus,
)
from fam_os.supervisor.ports import ServiceDefinitionProjector


class IdentityServiceDefinitionProjector:
    def project(self, definition: ServiceDefinition) -> ServiceDefinition:
        return definition


@dataclass(slots=True)
class SystemdUserServiceLifecycle:
    runner: CommandRunner
    settings: SystemdUserSettings = SystemdUserSettings()
    projector: ServiceDefinitionProjector = IdentityServiceDefinitionProjector()

    def start(self, definition: ServiceDefinition) -> ServiceStatus:
        command = build_start_command(self.projector.project(definition), self.settings)
        if self.runner.run(command, self.settings.timeout_seconds) is None:
            raise ServiceLifecycleError(f"could not start service {definition.service_id}")
        return self.status(definition.service_id)

    def stop(self, service_id: str) -> ServiceStatus:
        command = build_stop_command(service_id, self.settings)
        if self.runner.run(command, self.settings.timeout_seconds) is None:
            raise ServiceLifecycleError(f"could not stop service {service_id}")
        return self.status(service_id)

    def status(self, service_id: str) -> ServiceStatus:
        output = self.runner.run(
            build_show_command(service_id, self.settings), self.settings.timeout_seconds
        )
        if output is None:
            return ServiceStatus(service_id, ServiceState.UNKNOWN)
        return parse_service_status(service_id, output)

    def reset_failed(self, service_id: str) -> ServiceStatus:
        command = build_reset_failed_command(service_id, self.settings)
        if self.runner.run(command, self.settings.timeout_seconds) is None:
            raise ServiceLifecycleError(
                f"could not reset failed service {service_id}"
            )
        return self.status(service_id)

    def control_group(self, service_id: str) -> str | None:
        return self.status(service_id).resource_group
