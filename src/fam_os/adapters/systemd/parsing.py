"""Convert systemd property output into supervisor contracts."""

from fam_os.supervisor.contracts import ServiceState, ServiceStatus


def parse_properties(output: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)


def parse_service_status(service_id: str, output: str) -> ServiceStatus:
    values = parse_properties(output)
    state_value = values.get("ActiveState", ServiceState.UNKNOWN.value)
    try:
        state = ServiceState(state_value)
    except ValueError:
        state = ServiceState.UNKNOWN
    return ServiceStatus(
        service_id=service_id,
        state=state,
        substate=values.get("SubState") or None,
        result=values.get("Result") or None,
        main_pid=_positive_integer(values.get("MainPID")),
        resource_group=values.get("ControlGroup") or None,
    )


def _positive_integer(value: str | None) -> int | None:
    if value is None or not value.isdigit():
        return None
    parsed = int(value)
    return parsed if parsed > 0 else None
