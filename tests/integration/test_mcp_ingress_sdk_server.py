import unittest
from datetime import datetime, timedelta, timezone

try:
    from mcp.shared.memory import create_connected_server_and_client_session
except ImportError:
    MCP_SDK_AVAILABLE = False
else:
    MCP_SDK_AVAILABLE = True

from fam_os.adapters.mcp.ingress import (
    AuthenticatedMcpIngress, OfficialMcpIngressServer, OneTimeMcpIngressTokens,
)
from fam_os.core.admission import RequestIdentity
from fam_os.core.contracts import ResultStatus, TaskResult
from fam_os.core.ingress import IngressCapability


NOW = datetime(2026, 7, 16, 17, 0, tzinfo=timezone.utc)


@unittest.skipUnless(MCP_SDK_AVAILABLE, "official MCP SDK is not installed")
class McpIngressSdkServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_authenticated_catalog_and_tool_call_route_to_gateway(self):
        identity = RequestIdentity("user-live", "session-live", "authority-live")
        tokens = OneTimeMcpIngressTokens(clock=lambda: NOW)
        token = tokens.issue(identity, NOW + timedelta(minutes=5))
        gateway = Gateway()
        ingress = AuthenticatedMcpIngress.authenticate(
            token, tokens, gateway, request_id_factory=lambda: "request-live"
        )
        server = OfficialMcpIngressServer(ingress)

        async with create_connected_server_and_client_session(server.server) as client:
            listed = await client.list_tools()
            self.assertEqual(1, len(listed.tools))
            called = await client.call_tool(listed.tools[0].name, {"prompt": "hello"})
            self.assertFalse(called.isError)
            self.assertEqual("verified", called.structuredContent["status"])
            self.assertEqual("verified result", called.structuredContent["content"])
        self.assertEqual(identity, gateway.identity)


class Gateway:
    def __init__(self):
        self.identity = None
        self.capability = IngressCapability(
            "fam.ask", "Ask FAM", "Submit a verified local FAM request",
            {
                "type": "object", "properties": {"prompt": {"type": "string"}},
                "required": ["prompt"], "additionalProperties": False,
            },
            {"type": "object"},
        )

    async def visible_capabilities(self, identity):
        self.identity = identity
        return (self.capability,)

    async def invoke(self, identity, request):
        self.identity = identity
        return TaskResult(
            request.request_id, ResultStatus.VERIFIED, "verified result",
            verified=True, evidence_ids=("evidence-live",),
        )


if __name__ == "__main__":
    unittest.main()
