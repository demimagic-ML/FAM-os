import unittest
from datetime import datetime, timedelta, timezone

from fam_os.adapters.mcp.ingress import (
    AuthenticatedMcpIngress, McpIngressLimits, OneTimeMcpIngressTokens,
)
from fam_os.core.admission import RequestIdentity
from fam_os.core.contracts import ResultStatus, TaskResult
from fam_os.core.ingress import IngressCapability


NOW = datetime(2026, 7, 16, 17, 0, tzinfo=timezone.utc)


class McpIngressTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.identity = RequestIdentity("user-1", "session-1", "authority-1")
        self.tokens = OneTimeMcpIngressTokens(clock=lambda: NOW)
        self.gateway = Gateway()

    async def test_one_time_authentication_and_permission_filtered_call(self):
        token = self.tokens.issue(self.identity, NOW + timedelta(minutes=5))
        ingress = AuthenticatedMcpIngress.authenticate(
            token, self.tokens, self.gateway, request_id_factory=lambda: "request-1"
        )
        with self.assertRaises(PermissionError):
            AuthenticatedMcpIngress.authenticate(token, self.tokens, self.gateway)

        tools = await ingress.list_tools()
        self.assertEqual(1, len(tools))
        outcome = await ingress.call_tool(tools[0].name, {"prompt": "hello"})
        self.assertFalse(outcome.is_error)
        self.assertTrue(outcome.structured_content["verified"])
        identity, request = self.gateway.calls[-1]
        self.assertEqual(self.identity, identity)
        self.assertEqual("fam.ask", request.capability_id)

        with self.assertRaises(PermissionError):
            AuthenticatedMcpIngress(self.identity, self.gateway)

    async def test_permission_is_rechecked_at_call_time(self):
        ingress = self._ingress()
        tool = (await ingress.list_tools())[0]
        self.gateway.visible = False
        outcome = await ingress.call_tool(tool.name, {"prompt": "hello"})
        self.assertTrue(outcome.is_error)
        self.assertEqual("ingress.denied", outcome.structured_content["failure_code"])
        self.assertEqual([], self.gateway.calls)

    async def test_invalid_and_oversized_inputs_fail_before_gateway(self):
        ingress = self._ingress(McpIngressLimits(max_request_bytes=30))
        tool = (await ingress.list_tools())[0]
        invalid = await ingress.call_tool(tool.name, {})
        oversized = await ingress.call_tool(tool.name, {"prompt": "x" * 100})
        self.assertEqual("ingress.input_invalid", invalid.structured_content["failure_code"])
        self.assertEqual("ingress.request_too_large", oversized.structured_content["failure_code"])
        self.assertEqual([], self.gateway.calls)

    async def test_gateway_exception_and_large_result_are_content_free(self):
        ingress = self._ingress()
        tool = (await ingress.list_tools())[0]
        self.gateway.fail = True
        failed = await ingress.call_tool(tool.name, {"prompt": "hello"})
        self.assertEqual("ingress.gateway_failure", failed.structured_content["failure_code"])
        self.assertNotIn("private gateway detail", failed.safe_message)

        self.gateway.fail = False
        self.gateway.large = True
        small = self._ingress(McpIngressLimits(max_result_bytes=100))
        tool = (await small.list_tools())[0]
        limited = await small.call_tool(tool.name, {"prompt": "hello"})
        self.assertEqual("ingress.result_too_large", limited.structured_content["failure_code"])
        self.assertIsNone(limited.structured_content["content"])

    def test_expired_token_and_capacity_reject_without_storing_raw_token(self):
        token = self.tokens.issue(self.identity, NOW + timedelta(minutes=1))
        self.tokens.clock = lambda: NOW + timedelta(minutes=2)
        with self.assertRaises(PermissionError):
            self.tokens.authenticate(token)
        self.assertNotIn(token, repr(self.tokens))

    def _ingress(self, limits=McpIngressLimits()):
        token = self.tokens.issue(self.identity, NOW + timedelta(minutes=5))
        return AuthenticatedMcpIngress.authenticate(
            token, self.tokens, self.gateway, limits=limits,
            request_id_factory=lambda: "request-1",
        )


class Gateway:
    def __init__(self):
        self.visible = True
        self.calls = []
        self.fail = False
        self.large = False
        self.capability = IngressCapability(
            "fam.ask", "Ask FAM", "Submit an admitted FAM request",
            {
                "type": "object", "properties": {"prompt": {"type": "string"}},
                "required": ["prompt"], "additionalProperties": False,
            },
            {"type": "object"},
        )

    async def visible_capabilities(self, identity):
        return (self.capability,) if self.visible else ()

    async def invoke(self, identity, request):
        self.calls.append((identity, request))
        if self.fail:
            raise RuntimeError("private gateway detail")
        content = "x" * 1000 if self.large else "verified response"
        return TaskResult(
            request.request_id, ResultStatus.VERIFIED, content,
            verified=True, evidence_ids=("evidence-1",),
        )


if __name__ == "__main__":
    unittest.main()
