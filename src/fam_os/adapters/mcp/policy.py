"""Explicit allowlist, argument, and effect policy for one local MCP server."""

from dataclasses import dataclass
from enum import StrEnum

from fam_os.applications import (
    ApplicationAuthority, ApplicationIdentity, CapabilityKind,
    ConfirmationPolicy, Reversibility,
)
from fam_os.applications.identifiers import require_identifier
from fam_os.applications.payloads import freeze_payload


class McpArgumentSource(StrEnum):
    PROMPT = "prompt"
    RESOURCE_URI = "resource_uri"
    LITERAL = "literal"


@dataclass(frozen=True, slots=True)
class McpArgumentBinding:
    """Owner-approved source for one parameter of an observation tool."""

    parameter: str
    source: McpArgumentSource
    literal_value: object = None

    def __post_init__(self) -> None:
        if not self.parameter.strip():
            raise ValueError("MCP argument binding requires a parameter")
        if self.source is McpArgumentSource.LITERAL:
            frozen = freeze_payload({"value": self.literal_value})["value"]
            object.__setattr__(self, "literal_value", frozen)
        elif self.literal_value is not None:
            raise ValueError("non-literal MCP argument binding cannot contain a value")

    def resolve(self, prompt: str, resource_uri: str | None):
        if self.source is McpArgumentSource.PROMPT:
            return prompt
        if self.source is McpArgumentSource.RESOURCE_URI:
            if resource_uri is None:
                raise ValueError("MCP resource URI argument requires a selected resource")
            return resource_uri
        return _mutable(self.literal_value)


@dataclass(frozen=True, slots=True)
class McpToolPolicy:
    tool_name: str
    kind: CapabilityKind
    required_authority: ApplicationAuthority
    reversibility: Reversibility = Reversibility.NOT_APPLICABLE
    confirmation: ConfirmationPolicy = ConfirmationPolicy.NOT_REQUIRED
    postcondition_ids: tuple[str, ...] = ()
    resource_scopes: tuple[str, ...] = ()
    argument_bindings: tuple[McpArgumentBinding, ...] = ()

    def __post_init__(self) -> None:
        if not self.tool_name.strip():
            raise ValueError("MCP tool policy requires a tool name")
        if len(set(self.resource_scopes)) != len(self.resource_scopes):
            raise ValueError("MCP tool resource scopes must be unique")
        parameters = tuple(item.parameter for item in self.argument_bindings)
        if len(set(parameters)) != len(parameters):
            raise ValueError("MCP argument binding parameters must be unique")
        _validate_effect(self)

    def observation_arguments(
        self, prompt: str, resource_uri: str | None,
    ) -> dict[str, object]:
        if self.kind is not CapabilityKind.OBSERVATION:
            raise PermissionError("MCP action arguments come from approved action parameters")
        return {
            item.parameter: item.resolve(prompt, resource_uri)
            for item in self.argument_bindings
        }


@dataclass(frozen=True, slots=True)
class McpConnectorPolicy:
    server_id: str
    connector_id: str
    instance_id: str
    application: ApplicationIdentity
    allowed_resource_uris: tuple[str, ...]
    tool_policies: tuple[McpToolPolicy, ...]
    workspace_uris: tuple[str, ...] = ()
    allowed_protocol_versions: tuple[str, ...] = ("2025-11-25",)
    expected_server_name: str | None = None
    max_pages: int = 32
    max_primitives: int = 1024
    max_payload_bytes: int = 1_048_576
    operation_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        for name in ("server_id", "connector_id", "instance_id"):
            require_identifier(getattr(self, name), name)
        _unique(self.allowed_resource_uris, "resource allowlist")
        _unique(tuple(item.tool_name for item in self.tool_policies), "tool policies")
        _unique(self.workspace_uris, "workspace URIs")
        _unique(self.allowed_protocol_versions, "protocol versions")
        if self.expected_server_name is not None and not self.expected_server_name.strip():
            raise ValueError("expected MCP server name must not be empty")
        if min(self.max_pages, self.max_primitives, self.max_payload_bytes) <= 0:
            raise ValueError("MCP limits must be positive")
        if self.operation_timeout_seconds <= 0:
            raise ValueError("MCP operation timeout must be positive")

    def tool_policy(self, tool_name: str) -> McpToolPolicy | None:
        return next(
            (item for item in self.tool_policies if item.tool_name == tool_name), None
        )

    def authorize_server(self, name: str, protocol_version: str) -> None:
        if protocol_version not in self.allowed_protocol_versions:
            raise PermissionError("MCP protocol version is not approved")
        if self.expected_server_name is not None and name != self.expected_server_name:
            raise PermissionError("MCP server identity is not approved")


def _validate_effect(policy: McpToolPolicy) -> None:
    if policy.kind is CapabilityKind.OBSERVATION:
        if policy.required_authority is not ApplicationAuthority.OBSERVE:
            raise ValueError("MCP observation tool requires observe authority")
        if policy.reversibility is not Reversibility.NOT_APPLICABLE:
            raise ValueError("MCP observation tool cannot declare reversibility")
        if policy.confirmation is not ConfirmationPolicy.NOT_REQUIRED:
            raise ValueError("MCP observation tool cannot require confirmation")
        if policy.postcondition_ids:
            raise ValueError("MCP observation tool cannot declare postconditions")
        return
    if policy.argument_bindings:
        raise ValueError("MCP action tools cannot declare observation argument bindings")
    if policy.required_authority is ApplicationAuthority.OBSERVE:
        raise ValueError("MCP action tool requires action authority")
    if policy.reversibility is Reversibility.NOT_APPLICABLE:
        raise ValueError("MCP action tool must declare reversibility")
    if not policy.postcondition_ids:
        raise ValueError("MCP action tool requires deterministic postconditions")
    if (
        policy.reversibility is Reversibility.IRREVERSIBLE
        and policy.confirmation is not ConfirmationPolicy.ALWAYS
    ):
        raise ValueError("irreversible MCP tools always require confirmation")


def _unique(values: tuple[str, ...], name: str) -> None:
    if len(set(values)) != len(values) or any(not item.strip() for item in values):
        raise ValueError(f"MCP {name} must contain unique non-empty values")


def _mutable(value):
    if hasattr(value, "items"):
        return {key: _mutable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_mutable(item) for item in value]
    return value
