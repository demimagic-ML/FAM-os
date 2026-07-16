"""Independent MCP primitive classification into Application Fabric entries."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from jsonschema import Draft202012Validator

from fam_os.adapters.mcp.policy import McpConnectorPolicy
from fam_os.adapters.mcp.types import McpDiscoverySnapshot, mutable_json
from fam_os.applications import (
    ApplicationAuthority, ApplicationInstance, CapabilityDescriptor,
    CapabilityKind, CapabilityRegistryEntry, ConnectorRegistration, ConnectorTransportKind,
)


class McpPrimitiveKind(StrEnum):
    RESOURCE = "resource"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class McpCapabilityBinding:
    entry: CapabilityRegistryEntry
    primitive_kind: McpPrimitiveKind
    primitive_name: str
    input_schema: dict
    output_schema: dict
    output_required: bool = False


@dataclass(frozen=True, slots=True)
class McpMappedConnector:
    registration: ConnectorRegistration
    bindings: tuple[McpCapabilityBinding, ...]

    def binding(self, capability_id: str) -> McpCapabilityBinding:
        for item in self.bindings:
            if item.entry.capability_id == capability_id:
                return item
        raise KeyError("MCP capability is not registered")


def map_discovery(
    policy: McpConnectorPolicy, snapshot: McpDiscoverySnapshot, connected_at: datetime
) -> McpMappedConnector:
    instance = ApplicationInstance(
        policy.instance_id, policy.application, policy.connector_id,
        workspace_uris=policy.workspace_uris,
    )
    bindings = _resource_bindings(policy, snapshot, instance)
    bindings += _tool_bindings(policy, snapshot, instance)
    if not bindings:
        raise ValueError("MCP discovery has no approved capabilities")
    registration = ConnectorRegistration(
        policy.connector_id, ConnectorTransportKind.MCP_LOCAL, "mcp",
        snapshot.server.protocol_version, instance,
        tuple(item.entry for item in bindings), connected_at,
    )
    return McpMappedConnector(registration, bindings)


def _resource_bindings(policy, snapshot, instance):
    allowed = set(policy.allowed_resource_uris)
    input_schema = {"type": "object", "additionalProperties": False}
    output_schema = {"type": "object"}
    bindings = []
    for resource in snapshot.resources:
        if resource.uri not in allowed:
            continue
        capability = CapabilityDescriptor(
            _capability_id(policy.server_id, "resource", resource.uri),
            resource.name, resource.description or f"Read MCP resource {resource.uri}",
            CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
            _schema_id(input_schema), _schema_id(output_schema),
        )
        entry = _entry(instance, capability, (resource.uri,))
        bindings.append(McpCapabilityBinding(
            entry, McpPrimitiveKind.RESOURCE, resource.uri,
            input_schema, output_schema, False,
        ))
    return tuple(bindings)


def _tool_bindings(policy, snapshot, instance):
    bindings = []
    for tool in snapshot.tools:
        effect = policy.tool_policy(tool.name)
        if effect is None:
            continue
        input_schema = mutable_json(tool.input_schema)
        output_schema = mutable_json(tool.output_schema or {"type": "object"})
        _check_schema(input_schema)
        _check_schema(output_schema)
        capability = _tool_capability(policy, tool, effect, input_schema, output_schema)
        bindings.append(McpCapabilityBinding(
            _entry(instance, capability, effect.resource_scopes),
            McpPrimitiveKind.TOOL, tool.name, input_schema, output_schema,
            tool.output_schema is not None,
        ))
    return tuple(bindings)


def _tool_capability(policy, tool, effect, input_schema, output_schema):
    return CapabilityDescriptor(
        _capability_id(policy.server_id, "tool", tool.name),
        tool.name, tool.description or f"Invoke MCP tool {tool.name}",
        effect.kind, effect.required_authority,
        _schema_id(input_schema), _schema_id(output_schema),
        effect.reversibility, effect.confirmation, effect.postcondition_ids,
    )


def _entry(instance, capability, scopes):
    return CapabilityRegistryEntry(
        f"{instance.instance_id}:{capability.capability_id}",
        instance.connector_id, instance.instance_id,
        instance.application.application_id, capability, tuple(scopes),
    )


def _capability_id(server_id, primitive_kind, name):
    digest = hashlib.sha256(name.encode()).hexdigest()[:20]
    return f"mcp.{server_id}.{primitive_kind}.{digest}"


def _schema_id(schema):
    encoded = json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
    return f"mcp.schema.{hashlib.sha256(encoded).hexdigest()[:20]}"


def _check_schema(schema):
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        raise ValueError("MCP primitive contains an invalid JSON schema") from error
