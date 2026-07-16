"""Official MCP SDK low-level server over an authenticated ingress engine."""

from fam_os.adapters.mcp.ingress.engine import AuthenticatedMcpIngress
from fam_os.adapters.mcp.ingress.types import McpIngressOutcome
from fam_os.adapters.mcp.types import mutable_json


class OfficialMcpIngressServer:
    def __init__(self, ingress: AuthenticatedMcpIngress):
        try:
            from mcp import types
            from mcp.server.lowlevel import Server
        except ImportError as error:
            raise RuntimeError("MCP Python SDK v1 is not installed") from error
        self._types = types
        self.server = Server("FAM_OS", version="0.1.0")
        self._ingress = ingress
        self._register_handlers()

    def _register_handlers(self) -> None:
        types = self._types

        @self.server.list_tools()
        async def list_tools():
            try:
                tools = await self._ingress.list_tools()
            except Exception:
                tools = ()
            return [
                types.Tool(
                    name=item.name, title=item.title, description=item.description,
                    inputSchema=mutable_json(item.input_schema),
                    outputSchema=mutable_json(item.output_schema),
                    _meta={"fam/capabilityId": item.capability_id},
                )
                for item in tools
            ]

        @self.server.call_tool(validate_input=True)
        async def call_tool(name, arguments):
            try:
                outcome = await self._ingress.call_tool(name, arguments)
            except Exception:
                outcome = McpIngressOutcome(
                    True, "The request could not be completed.",
                    {
                        "request_id": "unavailable", "status": "failed",
                        "verified": False, "content": None,
                        "reason": "The request could not be completed.",
                        "evidence_ids": [],
                        "failure_code": "ingress.gateway_failure",
                    },
                )
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=outcome.safe_message)],
                structuredContent=mutable_json(outcome.structured_content),
                isError=outcome.is_error,
            )

    async def run(self, read_stream, write_stream) -> None:
        options = self.server.create_initialization_options()
        await self.server.run(read_stream, write_stream, options)

    async def run_stdio(self) -> None:
        from mcp.server.stdio import stdio_server
        async with stdio_server() as (read_stream, write_stream):
            await self.run(read_stream, write_stream)
