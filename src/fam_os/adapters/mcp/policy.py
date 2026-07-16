"""Explicit allowlist and effect policy for one local MCP server."""

from dataclasses import dataclass

from fam_os.applications import (
    ApplicationAuthority, ApplicationIdentity, CapabilityKind,
    ConfirmationPolicy, Reversibility,
)
from fam_os.applications.identifiers import require_identifier


@dataclass(frozen=True, slots=True)
class McpToolPolicy:
    tool_name: str
    kind: CapabilityKind
    required_authority: ApplicationAuthority
    reversibility: Reversibility = Reversibility.NOT_APPLICABLE
    confirmation: ConfirmationPolicy = ConfirmationPolicy.NOT_REQUIRED
    postcondition_ids: tuple[str, ...] = ()
    resource_scopes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.tool_name.strip():
            raise ValueError("MCP tool policy requires a tool name")
        if len(set(self.resource_scopes)) != len(self.resource_scopes):
            raise ValueError("MCP tool resource scopes must be unique")
        _validate_effect(self)


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
