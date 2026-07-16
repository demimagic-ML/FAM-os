"""Exact allowlisted primitive D-Bus calls through bounded busctl."""

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from fam_os.adapters.linux.bounded_command import BoundedSubprocessRunner
from fam_os.adapters.linux.deterministic_result import DeterministicAdapterResult
from fam_os.applications.payloads import freeze_payload


_BUS_NAME = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_-]*\.)+[A-Za-z_][A-Za-z0-9_-]*$")
_INTERFACE = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*\.)+[A-Za-z_][A-Za-z0-9_]*$")
_MEMBER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_OBJECT_PATH = re.compile(r"^/(?:[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*)?$")
_SIGNATURE = re.compile(r"^[A-Za-z0-9{}()av]+$")
_PRIMITIVE_SIGNATURES = frozenset("sbuityxdo g".replace(" ", ""))


class DbusBus(StrEnum):
    USER = "user"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class DbusParameter:
    name: str
    signature: str

    def __post_init__(self) -> None:
        if not _MEMBER.fullmatch(self.name) or self.signature not in _PRIMITIVE_SIGNATURES:
            raise ValueError("D-Bus parameter is invalid or unsupported")


@dataclass(frozen=True, slots=True)
class DbusCapabilitySpec:
    capability_id: str
    bus: DbusBus
    destination: str
    object_path: str
    interface: str
    member: str
    parameters: tuple[DbusParameter, ...]
    input_schema: dict

    def __post_init__(self) -> None:
        if not self.capability_id.strip():
            raise ValueError("D-Bus capability ID must not be empty")
        if not _BUS_NAME.fullmatch(self.destination) or not _INTERFACE.fullmatch(self.interface):
            raise ValueError("D-Bus destination or interface is invalid")
        if not _OBJECT_PATH.fullmatch(self.object_path):
            raise ValueError("D-Bus object path is invalid")
        if not _MEMBER.fullmatch(self.member):
            raise ValueError("D-Bus member is invalid")
        if len({item.name for item in self.parameters}) != len(self.parameters):
            raise ValueError("D-Bus parameter names must be unique")
        schema = freeze_payload(self.input_schema)
        Draft202012Validator.check_schema(_mutable(schema))
        object.__setattr__(self, "input_schema", schema)


class AllowlistedDbusAdapter:
    def __init__(
        self, capabilities: tuple[DbusCapabilitySpec, ...],
        busctl=Path("/usr/bin/busctl"), environment=None, runner=None,
    ):
        self._capabilities = {item.capability_id: item for item in capabilities}
        if len(self._capabilities) != len(capabilities):
            raise ValueError("D-Bus capability IDs must be unique")
        self._busctl = busctl
        self._environment = dict(environment or {})
        self._runner = runner or BoundedSubprocessRunner()

    def invoke(self, capability_id: str, arguments: dict):
        spec = self._capabilities.get(capability_id)
        if spec is None:
            raise PermissionError("D-Bus capability is not allowlisted")
        try:
            Draft202012Validator(_mutable(spec.input_schema)).validate(arguments)
        except ValidationError as error:
            raise ValueError("D-Bus arguments failed the capability schema") from error
        command = _command(self._busctl, spec, arguments)
        try:
            result = self._runner.run(command, environment=self._environment)
        except Exception:
            return _failed(capability_id, "dbus.provider_failure")
        if not result.succeeded:
            code = "dbus.output_limit" if result.output_limited else "dbus.call_failed"
            return _failed(capability_id, code)
        return DeterministicAdapterResult(
            capability_id, True, {"reply": result.stdout.strip()}
        )


def session_bus_environment(environment):
    allowed = ("DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "LANG", "LC_ALL")
    return {name: environment[name] for name in allowed if environment.get(name)}


def _command(executable, spec, arguments):
    command = [str(executable), f"--{spec.bus.value}", "call"]
    command.extend((spec.destination, spec.object_path, spec.interface, spec.member))
    if spec.parameters:
        command.append("".join(item.signature for item in spec.parameters))
        command.extend(_encode(item.signature, arguments[item.name]) for item in spec.parameters)
    return tuple(command)


def _encode(signature, value):
    if signature == "b" and isinstance(value, bool):
        return "true" if value else "false"
    if signature in "uityx" and _integer_in_range(signature, value):
        return str(value)
    if signature == "d" and isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if signature in "sog" and isinstance(value, str) and "\0" not in value:
        if signature == "o" and not _OBJECT_PATH.fullmatch(value):
            raise ValueError("D-Bus object path argument is invalid")
        if signature == "g" and not _SIGNATURE.fullmatch(value):
            raise ValueError("D-Bus signature argument is invalid")
        return value
    raise ValueError("D-Bus argument type does not match its signature")


def _failed(capability_id, code):
    return DeterministicAdapterResult(capability_id, False, {}, code)


def _integer_in_range(signature, value):
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    ranges = {
        "y": (0, 2**8 - 1), "u": (0, 2**32 - 1),
        "i": (-(2**31), 2**31 - 1), "t": (0, 2**64 - 1),
        "x": (-(2**63), 2**63 - 1),
    }
    low, high = ranges[signature]
    return low <= value <= high


def _mutable(value):
    if hasattr(value, "items"):
        return {key: _mutable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_mutable(item) for item in value]
    return value
