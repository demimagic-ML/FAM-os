"""Explicit owner-controlled configuration and lifecycle for local MCP clients."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from fam_os.adapters.mcp.mapping import McpPrimitiveKind
from fam_os.adapters.mcp.policy import (
    McpArgumentBinding, McpArgumentSource, McpConnectorPolicy, McpToolPolicy,
)
from fam_os.adapters.mcp.sdk import McpStdioConfiguration
from fam_os.applications import (
    ApplicationAuthority, ApplicationIdentity, CapabilityKind,
    ConfirmationPolicy, Reversibility,
)
from fam_os.product.composition.mcp_transport import McpApplicationTransport
from fam_os.product.composition.mcp_worker import McpClientWorker


MCP_CONFIG_VERSION = "fam.product.mcp-clients/v1alpha1"


@dataclass(frozen=True, slots=True)
class McpClientDefinition:
    transport: McpStdioConfiguration
    policy: McpConnectorPolicy


class ProductMcpClients:
    def __init__(self, registry, definitions: tuple[McpClientDefinition, ...]) -> None:
        self._registry = registry
        self._definitions = definitions
        self._transports: dict[str, McpApplicationTransport] = {}

    @classmethod
    def from_file(cls, registry, path: Path) -> "ProductMcpClients":
        if not path.exists():
            return cls(registry, ())
        _require_private(path)
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("contract_version") != MCP_CONFIG_VERSION:
            raise ValueError("MCP client configuration version is unsupported")
        servers = document.get("servers")
        if not isinstance(servers, list) or len(servers) > 32:
            raise ValueError("MCP client configuration servers are invalid")
        definitions = tuple(_definition(item) for item in servers)
        connector_ids = tuple(item.policy.connector_id for item in definitions)
        if len(set(connector_ids)) != len(connector_ids):
            raise ValueError("MCP connector IDs must be unique")
        return cls(registry, definitions)

    def start(self) -> None:
        started = []
        try:
            for definition in self._definitions:
                worker = McpClientWorker(definition.transport, definition.policy)
                transport = None
                try:
                    mapped = worker.start()
                    _validate_observation_bindings(definition.policy, mapped)
                    transport = McpApplicationTransport(
                        worker, mapped, definition.policy,
                    )
                    self._registry.register(mapped.registration)
                except BaseException:
                    if transport is None:
                        worker.stop()
                    else:
                        transport.close()
                    raise
                self._transports[transport.connector_id] = transport
                started.append(transport)
        except BaseException:
            for transport in reversed(started):
                self._registry.unregister(transport.connector_id)
                transport.close()
            self._transports.clear()
            raise

    def transport(self, connector_id: str) -> McpApplicationTransport | None:
        return self._transports.get(connector_id)

    def close(self) -> None:
        for connector_id, transport in tuple(self._transports.items()):
            self._registry.unregister(connector_id)
            transport.close()
        self._transports.clear()


def _definition(value) -> McpClientDefinition:
    if not isinstance(value, dict):
        raise ValueError("MCP server definition must be an object")
    application = value.get("application")
    if not isinstance(application, dict):
        raise ValueError("MCP application identity is required")
    identity = ApplicationIdentity(
        application["application_id"], application["display_name"],
        application.get("vendor"), application.get("version"),
    )
    transport = McpStdioConfiguration(
        Path(value["command"]), tuple(value.get("arguments", ())),
        tuple(sorted(_environment(value.get("environment", {})).items())),
        _optional_path(value.get("working_directory")),
    )
    policies = tuple(_tool_policy(item) for item in value.get("tools", ()))
    policy = McpConnectorPolicy(
        value["server_id"], value["connector_id"], value["instance_id"], identity,
        tuple(value.get("allowed_resource_uris", ())), policies,
        tuple(value.get("workspace_uris", ())),
        tuple(value.get("allowed_protocol_versions", ("2025-11-25",))),
        value.get("expected_server_name"),
        int(value.get("max_pages", 32)), int(value.get("max_primitives", 1024)),
        int(value.get("max_payload_bytes", 1_048_576)),
        float(value.get("operation_timeout_seconds", 30)),
    )
    return McpClientDefinition(transport, policy)


def _tool_policy(value) -> McpToolPolicy:
    if not isinstance(value, dict):
        raise ValueError("MCP tool policy must be an object")
    return McpToolPolicy(
        value["tool_name"], CapabilityKind(value["kind"]),
        ApplicationAuthority(value["required_authority"]),
        Reversibility(value.get("reversibility", "not_applicable")),
        ConfirmationPolicy(value.get("confirmation", "not_required")),
        tuple(value.get("postcondition_ids", ())),
        tuple(value.get("resource_scopes", ())),
        tuple(_argument_binding(item) for item in value.get("argument_bindings", ())),
    )


def _argument_binding(value) -> McpArgumentBinding:
    if not isinstance(value, dict):
        raise ValueError("MCP argument binding must be an object")
    source = McpArgumentSource(value.get("source"))
    fields = {"parameter", "source"}
    if source is McpArgumentSource.LITERAL:
        fields.add("value")
    if set(value) != fields:
        raise ValueError("MCP argument binding fields are invalid")
    return McpArgumentBinding(
        value["parameter"], source, value.get("value"),
    )


def _environment(value) -> dict[str, str]:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in value.items()
    ):
        raise ValueError("MCP environment must be a string map")
    return value


def _optional_path(value) -> Path | None:
    return None if value is None else Path(value)


def _require_private(path: Path) -> None:
    stat = path.stat()
    if path.is_symlink() or not path.is_file() or stat.st_uid != os.geteuid():
        raise PermissionError("MCP configuration must be an owner-controlled file")
    if stat.st_mode & 0o077:
        raise PermissionError("MCP configuration must not be accessible to group or others")


def _validate_observation_bindings(policy, mapped) -> None:
    for mapped_binding in mapped.bindings:
        if mapped_binding.primitive_kind is not McpPrimitiveKind.TOOL:
            continue
        tool_policy = policy.tool_policy(mapped_binding.primitive_name)
        if tool_policy is None or tool_policy.kind is not CapabilityKind.OBSERVATION:
            continue
        schema = mapped_binding.input_schema
        properties = schema.get("properties", {})
        required = schema.get("required", ())
        if not isinstance(properties, dict) or not isinstance(required, (list, tuple)):
            raise ValueError("MCP observation input schema fields are invalid")
        configured = {item.parameter for item in tool_policy.argument_bindings}
        if not configured <= set(properties):
            raise ValueError("MCP observation binding targets an undeclared parameter")
        if not set(required) <= configured:
            raise ValueError("MCP observation required parameters must be explicitly bound")
        for binding in tool_policy.argument_bindings:
            if binding.source is not McpArgumentSource.LITERAL:
                continue
            try:
                Draft202012Validator(properties[binding.parameter]).validate(
                    binding.literal_value,
                )
            except ValidationError as error:
                raise ValueError(
                    "MCP literal argument does not satisfy its declared schema"
                ) from error
