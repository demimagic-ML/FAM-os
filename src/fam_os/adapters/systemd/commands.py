"""Pure command construction for user-scoped systemd operations."""

from fam_os.adapters.systemd.settings import SystemdUserSettings
from fam_os.supervisor.contracts import ResourceLimits, ServiceDefinition


STATUS_PROPERTIES = (
    "ActiveState",
    "SubState",
    "Result",
    "MainPID",
    "ControlGroup",
)


def canonical_unit(service_id: str) -> str:
    return service_id if service_id.endswith(".service") else f"{service_id}.service"


def build_start_command(
    definition: ServiceDefinition, settings: SystemdUserSettings
) -> tuple[str, ...]:
    command = [
        settings.systemd_run_command,
        "--user",
        f"--unit={canonical_unit(definition.service_id)}",
    ]
    collection = (
        "--property=CollectMode=inactive"
        if settings.retain_failed_state else "--collect"
    )
    command.append(collection)
    command.extend((
        "--property=KillMode=control-group",
        "--property=SendSIGKILL=yes",
        f"--property=TimeoutStopSec={settings.stop_grace_seconds:g}s",
    ))
    if settings.apparmor_profile is not None:
        command.append(f"--property=AppArmorProfile={settings.apparmor_profile}")
    command.extend(_limit_arguments(definition.limits))
    command.extend(f"--setenv={key}={value}" for key, value in definition.environment)
    command.extend(("--", *definition.command))
    return tuple(command)


def build_stop_command(service_id: str, settings: SystemdUserSettings) -> tuple[str, ...]:
    return settings.systemctl_command, "--user", "stop", canonical_unit(service_id)


def build_reset_failed_command(
    service_id: str, settings: SystemdUserSettings
) -> tuple[str, ...]:
    return (
        settings.systemctl_command, "--user", "reset-failed",
        canonical_unit(service_id),
    )


def build_show_command(service_id: str, settings: SystemdUserSettings) -> tuple[str, ...]:
    command = [settings.systemctl_command, "--user", "show", canonical_unit(service_id)]
    command.extend(f"--property={name}" for name in STATUS_PROPERTIES)
    command.append("--no-pager")
    return tuple(command)


def _limit_arguments(limits: ResourceLimits) -> tuple[str, ...]:
    values: list[str] = []
    if limits.memory_max_bytes is not None:
        values.append(f"--property=MemoryMax={limits.memory_max_bytes}")
    if limits.swap_max_bytes is not None:
        values.append(f"--property=MemorySwapMax={limits.swap_max_bytes}")
    if limits.cpu_quota_percent is not None:
        values.append(f"--property=CPUQuota={limits.cpu_quota_percent:g}%")
    if limits.tasks_max is not None:
        values.append(f"--property=TasksMax={limits.tasks_max}")
    for item in limits.block_io_bandwidth:
        if item.read_bytes_per_second is not None:
            values.append(
                f"--property=IOReadBandwidthMax={item.device_path} {item.read_bytes_per_second}"
            )
        if item.write_bytes_per_second is not None:
            values.append(
                f"--property=IOWriteBandwidthMax={item.device_path} {item.write_bytes_per_second}"
            )
    return tuple(values)
