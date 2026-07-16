import unittest

from fam_os.adapters.mcp import (
    McpCallResult, McpClientAdapter, McpConnectorPolicy, McpReadResult,
    McpConnectorLifecycle, McpResource, McpResourcePage, McpServerInfo, McpTool, McpToolPage,
    McpToolPolicy,
)
from fam_os.applications import (
    ApplicationAuthority, ApplicationIdentity, CapabilityKind,
    ApplicationCapabilityRegistry, ConfirmationPolicy, Reversibility,
)


class McpClientAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = FakeMcpSession()
        self.adapter = McpClientAdapter(self.session, _policy())

    async def test_discovery_is_paginated_allowlisted_and_independently_classified(self):
        mapped = await self.adapter.initialize()
        self.assertEqual("mcp_local", mapped.registration.transport_kind.value)
        self.assertEqual("2025-11-25", mapped.registration.protocol_version)
        self.assertEqual(3, len(mapped.bindings))
        self.assertEqual(
            {"Allowed document", "search", "write_file"},
            {item.entry.capability.display_name for item in mapped.bindings},
        )
        kinds = {
            item.primitive_name: item.entry.capability.kind for item in mapped.bindings
        }
        self.assertEqual(CapabilityKind.OBSERVATION, kinds["search"])
        self.assertEqual(CapabilityKind.ACTION, kinds["write_file"])
        self.assertNotIn("denied_tool", kinds)

    async def test_resource_observation_and_tool_invocation_are_bounded_outcomes(self):
        mapped = await self.adapter.initialize()
        resource = _binding(mapped, "fam-test://allowed")
        search = _binding(mapped, "search")
        action = _binding(mapped, "write_file")

        observed = await self.adapter.observe(resource.entry.capability_id, {})
        searched = await self.adapter.observe(search.entry.capability_id, {"query": "FAM"})
        executed = await self.adapter.execute(action.entry.capability_id, {"text": "new"})

        self.assertTrue(observed.succeeded)
        self.assertEqual("allowed", observed.payload["contents"][0]["text"])
        self.assertTrue(searched.succeeded)
        self.assertEqual("FAM", searched.payload["structured_content"]["result"])
        self.assertTrue(executed.succeeded)
        self.assertEqual(["search", "write_file"], [item[0] for item in self.session.calls])

    async def test_effect_boundary_and_input_schema_fail_before_provider_call(self):
        mapped = await self.adapter.initialize()
        search = _binding(mapped, "search")
        action = _binding(mapped, "write_file")
        with self.assertRaises(PermissionError):
            await self.adapter.execute(search.entry.capability_id, {"query": "x"})
        with self.assertRaises(PermissionError):
            await self.adapter.observe(action.entry.capability_id, {"text": "x"})
        with self.assertRaisesRegex(ValueError, "declared schema"):
            await self.adapter.observe(search.entry.capability_id, {})
        self.assertEqual([], self.session.calls)

    async def test_provider_and_output_failures_are_safe_and_do_not_expose_payload(self):
        mapped = await self.adapter.initialize()
        action = _binding(mapped, "write_file")
        self.session.bad_output = True
        outcome = await self.adapter.execute(action.entry.capability_id, {"text": "new"})
        self.assertFalse(outcome.succeeded)
        self.assertEqual("mcp.output_schema_invalid", outcome.error_code)
        self.assertEqual({}, dict(outcome.payload))

        self.session.provider_failure = True
        outcome = await self.adapter.execute(action.entry.capability_id, {"text": "new"})
        self.assertEqual("mcp.provider_failure", outcome.error_code)
        self.assertNotIn("secret provider detail", str(outcome.payload))

        self.session.provider_failure = False
        self.session.tool_error = True
        outcome = await self.adapter.execute(action.entry.capability_id, {"text": "new"})
        self.assertEqual("mcp.tool_error", outcome.error_code)
        self.assertNotIn("server secret", str(outcome.payload))

    async def test_payload_limit_discards_oversized_provider_data(self):
        adapter = McpClientAdapter(FakeMcpSession(), _policy(max_payload_bytes=10))
        mapped = await adapter.initialize()
        resource = _binding(mapped, "fam-test://allowed")
        outcome = await adapter.observe(resource.entry.capability_id, {})
        self.assertEqual("mcp.payload_limit_exceeded", outcome.error_code)
        self.assertEqual({}, dict(outcome.payload))

    async def test_refresh_reuses_initialized_session_and_close_is_forwarded(self):
        first = await self.adapter.initialize()
        with self.assertRaisesRegex(RuntimeError, "already initialized"):
            await self.adapter.initialize()
        refreshed = await self.adapter.refresh()
        self.assertEqual(first.registration.protocol_version, refreshed.registration.protocol_version)
        self.assertEqual(1, self.session.initialize_count)
        await self.adapter.close()
        self.assertTrue(self.session.closed)
        with self.assertRaises(RuntimeError):
            _ = self.adapter.mapped

    async def test_unapproved_protocol_or_server_identity_rejects_before_discovery(self):
        session = FakeMcpSession()
        session.server = McpServerInfo("wrong-server", "1.0", "2025-11-25")
        policy = _policy(expected_server_name="expected-server")
        with self.assertRaisesRegex(PermissionError, "identity"):
            await McpClientAdapter(session, policy).initialize()
        self.assertEqual(0, session.discovery_calls)

        session = FakeMcpSession()
        session.server = McpServerInfo("test-server", "1.0", "draft-version")
        with self.assertRaisesRegex(PermissionError, "version"):
            await McpClientAdapter(session, _policy()).initialize()

    async def test_repeated_pagination_cursor_and_primitive_limit_reject(self):
        self.session.repeat_cursor = True
        with self.assertRaisesRegex(ValueError, "cursor repeated"):
            await self.adapter.initialize()
        limited = McpClientAdapter(FakeMcpSession(), _policy(max_primitives=1))
        with self.assertRaisesRegex(ValueError, "primitive limit"):
            await limited.initialize()

    async def test_lifecycle_registers_refreshes_and_unregisters_atomically(self):
        registry = ApplicationCapabilityRegistry()
        lifecycle = McpConnectorLifecycle(self.adapter, registry)
        registration = await lifecycle.start()
        self.assertEqual(
            {item.entry_id for item in registration.capabilities},
            {item.entry_id for item in registry.entries()},
        )
        await lifecycle.refresh()
        self.assertEqual(2, registry.snapshot().revision)
        await lifecycle.stop()
        self.assertEqual((), registry.entries())
        self.assertTrue(self.session.closed)


class FakeMcpSession:
    def __init__(self):
        self.initialize_count = 0
        self.calls = []
        self.closed = False
        self.repeat_cursor = False
        self.bad_output = False
        self.provider_failure = False
        self.tool_error = False
        self.server = McpServerInfo("test-server", "1.0", "2025-11-25")
        self.discovery_calls = 0

    async def initialize(self):
        self.initialize_count += 1
        return self.server

    async def list_resources(self, cursor=None):
        self.discovery_calls += 1
        if cursor is None:
            return McpResourcePage(
                (McpResource("fam-test://allowed", "Allowed document"),), "resources-2"
            )
        next_cursor = "resources-2" if self.repeat_cursor else None
        return McpResourcePage(
            (McpResource("fam-test://denied", "Denied document"),), next_cursor
        )

    async def list_tools(self, cursor=None):
        self.discovery_calls += 1
        tools = (
            McpTool(
                "search", "Search", _object_schema("query"),
                _object_schema("result"), {"destructiveHint": True},
            ),
            McpTool(
                "write_file", "Write", _object_schema("text"),
                _object_schema("changed"), {"readOnlyHint": True},
            ),
            McpTool("denied_tool", "Denied", {"type": "object"}),
        )
        return McpToolPage(tools)

    async def read_resource(self, uri):
        return McpReadResult(({"uri": uri, "text": "allowed"},))

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.provider_failure:
            raise RuntimeError("secret provider detail")
        if self.tool_error:
            return McpCallResult(
                True, ({"type": "text", "text": "server secret"},)
            )
        if name == "search":
            structured = {"result": arguments["query"]}
        else:
            structured = {"wrong": True} if self.bad_output else {"changed": True}
        return McpCallResult(False, ({"type": "text", "text": "ok"},), structured)

    async def close(self):
        self.closed = True


def _policy(
    max_primitives=20, expected_server_name=None, max_payload_bytes=1_048_576
):
    return McpConnectorPolicy(
        "server-1", "connector-mcp-1", "instance-mcp-1",
        ApplicationIdentity("app.mcp-test", "MCP test application"),
        ("fam-test://allowed",),
        (
            McpToolPolicy(
                "search", CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE
            ),
            McpToolPolicy(
                "write_file", CapabilityKind.ACTION, ApplicationAuthority.MODIFY,
                Reversibility.REVERSIBLE, ConfirmationPolicy.ALWAYS,
                ("file.hash",), ("file:///workspace",),
            ),
        ),
        expected_server_name=expected_server_name,
        max_primitives=max_primitives,
        max_payload_bytes=max_payload_bytes,
    )


def _object_schema(required_name):
    return {
        "type": "object", "properties": {required_name: {}},
        "required": [required_name], "additionalProperties": False,
    }


def _binding(mapped, primitive_name):
    return next(item for item in mapped.bindings if item.primitive_name == primitive_name)


if __name__ == "__main__":
    unittest.main()
