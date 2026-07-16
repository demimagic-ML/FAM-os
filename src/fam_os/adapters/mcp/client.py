"""Bounded MCP discovery and invocation over the provider port."""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from jsonschema import Draft202012Validator, ValidationError

from fam_os.adapters.mcp.mapping import (
    McpMappedConnector, McpPrimitiveKind, map_discovery,
)
from fam_os.adapters.mcp.policy import McpConnectorPolicy
from fam_os.adapters.mcp.ports import McpClientSessionPort
from fam_os.adapters.mcp.types import (
    McpCallResult, McpDiscoverySnapshot, mutable_json,
)
from fam_os.applications import CapabilityKind
from fam_os.applications.payloads import JsonObject, freeze_payload


@dataclass(frozen=True, slots=True)
class McpOperationOutcome:
    capability_id: str
    succeeded: bool
    payload: JsonObject
    error_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", freeze_payload(self.payload))
        if self.succeeded == (self.error_code is not None):
            raise ValueError("MCP outcome success and error code disagree")


class McpClientAdapter:
    def __init__(self, session: McpClientSessionPort, policy: McpConnectorPolicy):
        self._session = session
        self._policy = policy
        self._mapped = None
        self._server = None
        self._lock = asyncio.Lock()

    @property
    def mapped(self) -> McpMappedConnector:
        if self._mapped is None:
            raise RuntimeError("MCP client is not initialized")
        return self._mapped

    async def initialize(self) -> McpMappedConnector:
        async with self._lock:
            if self._mapped is not None:
                raise RuntimeError("MCP client is already initialized; use refresh")
            server = await self._await(self._session.initialize())
            self._policy.authorize_server(server.name, server.protocol_version)
            self._server = server
            resources = await self._collect_pages(self._session.list_resources)
            tools = await self._collect_pages(self._session.list_tools)
            snapshot = McpDiscoverySnapshot(server, resources, tools)
            self._mapped = map_discovery(
                self._policy, snapshot, datetime.now(timezone.utc)
            )
            return self._mapped

    async def refresh(self) -> McpMappedConnector:
        async with self._lock:
            if self._mapped is None:
                raise RuntimeError("MCP client is not initialized")
            resources = await self._collect_pages(self._session.list_resources)
            tools = await self._collect_pages(self._session.list_tools)
            snapshot = McpDiscoverySnapshot(
                self._server, resources, tools,
            )
            self._mapped = map_discovery(
                self._policy, snapshot, datetime.now(timezone.utc)
            )
            return self._mapped

    async def observe(self, capability_id: str, arguments: dict) -> McpOperationOutcome:
        async with self._lock:
            binding = self.mapped.binding(capability_id)
            if binding.entry.capability.kind is not CapabilityKind.OBSERVATION:
                raise PermissionError("MCP action capability cannot be observed")
            _validate(arguments, binding.input_schema)
            if binding.primitive_kind is McpPrimitiveKind.RESOURCE:
                try:
                    result = await self._await(
                        self._session.read_resource(binding.primitive_name)
                    )
                except Exception:
                    return self._provider_failure(capability_id)
                payload = {"contents": [mutable_json(item) for item in result.contents]}
                return self._bounded(capability_id, True, payload)
            return await self._invoke_tool(binding, arguments)

    async def execute(self, capability_id: str, arguments: dict) -> McpOperationOutcome:
        async with self._lock:
            binding = self.mapped.binding(capability_id)
            if binding.entry.capability.kind is not CapabilityKind.ACTION:
                raise PermissionError("MCP observation capability cannot execute")
            _validate(arguments, binding.input_schema)
            return await self._invoke_tool(binding, arguments)

    async def close(self) -> None:
        async with self._lock:
            self._mapped = None
            self._server = None
            # AnyIO context managers used by the official SDK must exit in the
            # same task that entered them, so close must not use wait_for.
            await self._session.close()

    async def _collect_pages(self, method):
        cursor = None
        seen = set()
        items = []
        for _ in range(self._policy.max_pages):
            page = await self._await(method(cursor))
            items.extend(page.items)
            if len(items) > self._policy.max_primitives:
                raise ValueError("MCP primitive limit exceeded")
            cursor = page.next_cursor
            if cursor is None:
                return tuple(items)
            if cursor in seen:
                raise ValueError("MCP pagination cursor repeated")
            seen.add(cursor)
        raise ValueError("MCP pagination page limit exceeded")

    async def _invoke_tool(self, binding, arguments):
        capability_id = binding.entry.capability_id
        try:
            result = await self._await(
                self._session.call_tool(binding.primitive_name, arguments)
            )
        except Exception:
            return self._provider_failure(capability_id)
        if result.is_error:
            return self._call_outcome(capability_id, result)
        if binding.output_required:
            if result.structured_content is None:
                return McpOperationOutcome(
                    capability_id, False, {}, "mcp.output_schema_invalid"
                )
            try:
                _validate(mutable_json(result.structured_content), binding.output_schema)
            except ValueError:
                return McpOperationOutcome(
                    capability_id, False, {}, "mcp.output_schema_invalid"
                )
        return self._call_outcome(capability_id, result)

    def _call_outcome(self, capability_id: str, result: McpCallResult):
        if result.is_error:
            return McpOperationOutcome(capability_id, False, {}, "mcp.tool_error")
        payload = {
            "content": [mutable_json(item) for item in result.content],
            "structured_content": mutable_json(result.structured_content),
        }
        return self._bounded(capability_id, True, payload)

    @staticmethod
    def _provider_failure(capability_id):
        return McpOperationOutcome(capability_id, False, {}, "mcp.provider_failure")

    async def _await(self, operation):
        return await asyncio.wait_for(
            operation, timeout=self._policy.operation_timeout_seconds
        )

    def _bounded(self, capability_id, succeeded, payload, error_code=None):
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded) > self._policy.max_payload_bytes:
            return McpOperationOutcome(
                capability_id, False, {}, "mcp.payload_limit_exceeded"
            )
        return McpOperationOutcome(capability_id, succeeded, payload, error_code)


def _validate(arguments, schema):
    try:
        Draft202012Validator(schema).validate(arguments)
    except ValidationError as error:
        raise ValueError("MCP capability input failed its declared schema") from error
