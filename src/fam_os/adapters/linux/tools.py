"""Allowlisted shell-free deterministic tool capability adapter."""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from fam_os.adapters.linux.bounded_command import BoundedSubprocessRunner
from fam_os.adapters.linux.deterministic_result import DeterministicAdapterResult
from fam_os.applications.payloads import freeze_payload


class ToolOutputKind(StrEnum):
    TEXT = "text"
    JSON = "json"


@dataclass(frozen=True, slots=True)
class ToolParameter:
    name: str
    flag: str | None = None
    boolean_flag: bool = False

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("tool parameter name must not be empty")
        if self.flag is not None and (not self.flag.startswith("-") or "\0" in self.flag):
            raise ValueError("tool parameter flag is invalid")


@dataclass(frozen=True, slots=True)
class ToolCapabilitySpec:
    capability_id: str
    executable: Path
    fixed_arguments: tuple[str, ...]
    parameters: tuple[ToolParameter, ...]
    input_schema: dict
    output_kind: ToolOutputKind = ToolOutputKind.TEXT
    working_directory: Path | None = None
    environment: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.capability_id.strip() or not self.executable.is_absolute():
            raise ValueError("tool capability identity or executable is invalid")
        if any("\0" in item for item in self.fixed_arguments):
            raise ValueError("tool fixed arguments cannot contain null bytes")
        if len({item.name for item in self.parameters}) != len(self.parameters):
            raise ValueError("tool parameter names must be unique")
        if len({key for key, _ in self.environment}) != len(self.environment):
            raise ValueError("tool environment keys must be unique")
        if any(
            not key or "=" in key or "\0" in key or "\0" in value
            for key, value in self.environment
        ):
            raise ValueError("tool environment is invalid")
        if self.working_directory is not None and not self.working_directory.is_absolute():
            raise ValueError("tool working directory must be absolute")
        schema = freeze_payload(self.input_schema)
        Draft202012Validator.check_schema(_mutable(schema))
        object.__setattr__(self, "input_schema", schema)


class AllowlistedToolAdapter:
    def __init__(self, capabilities: tuple[ToolCapabilitySpec, ...], runner=None):
        self._capabilities = {item.capability_id: item for item in capabilities}
        if len(self._capabilities) != len(capabilities):
            raise ValueError("tool capability IDs must be unique")
        self._runner = runner or BoundedSubprocessRunner()

    def invoke(self, capability_id: str, arguments: dict):
        spec = self._capabilities.get(capability_id)
        if spec is None:
            raise PermissionError("tool capability is not allowlisted")
        try:
            Draft202012Validator(_mutable(spec.input_schema)).validate(arguments)
            command = _command(spec, arguments)
        except (ValidationError, ValueError) as error:
            raise ValueError("tool arguments failed the capability schema") from error
        try:
            result = self._runner.run(
                command, cwd=spec.working_directory,
                environment=dict(spec.environment),
            )
        except Exception:
            return _failed(capability_id, "tool.provider_failure")
        if not result.succeeded:
            code = "tool.output_limit" if result.output_limited else "tool.execution_failed"
            return _failed(capability_id, code)
        return _success(spec, result.stdout)


def _command(spec, arguments):
    command = [str(spec.executable), *spec.fixed_arguments]
    for parameter in spec.parameters:
        if parameter.name not in arguments:
            continue
        value = arguments[parameter.name]
        if parameter.boolean_flag:
            if not isinstance(value, bool):
                raise ValueError("boolean tool parameter must be boolean")
            if value and parameter.flag is not None:
                command.append(parameter.flag)
            continue
        if parameter.flag is not None:
            command.append(parameter.flag)
        command.append(_primitive(value))
    return tuple(command)


def _primitive(value):
    if isinstance(value, str) and "\0" not in value:
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    raise ValueError("tool parameter must be a string or number")


def _success(spec, stdout):
    if spec.output_kind is ToolOutputKind.TEXT:
        return DeterministicAdapterResult(spec.capability_id, True, {"text": stdout})
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError:
        return _failed(spec.capability_id, "tool.output_invalid")
    if not isinstance(value, dict):
        return _failed(spec.capability_id, "tool.output_invalid")
    return DeterministicAdapterResult(spec.capability_id, True, {"json": value})


def _failed(capability_id, code):
    return DeterministicAdapterResult(capability_id, False, {}, code)


def _mutable(value):
    if hasattr(value, "items"):
        return {key: _mutable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_mutable(item) for item in value]
    return value
