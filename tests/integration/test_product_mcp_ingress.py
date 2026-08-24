import json
import os
import tempfile
import unittest
from pathlib import Path
import sys

from fam_os.adapters.mcp import McpStdioConfiguration, OfficialMcpStdioSession
from fam_os.adapters.mcp.ingress import UnixMcpIngressClient
from fam_os.core.ports import InferenceResponse
from fam_os.product.service import LocalProductService, ProductServiceSettings
from fam_os.telemetry import InferenceMetrics
from tests.integration.product_runtime_fixture import (
    ContextProfileFixture,
    ResidentRuntimeFixture,
)


class _Runtime(ResidentRuntimeFixture):
    def __init__(self):
        super().__init__()

    def chat(self, request):
        return InferenceResponse(
            "MCP entered durable FAM Core",
            InferenceMetrics(request.model_ref, 0.01, 0.0, 8, 4, 400.0),
        )

class ProductMcpIngressTests(unittest.IsolatedAsyncioTestCase):
    async def test_allowlisted_client_calls_same_durable_core_lifecycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state, runtime = root / "state", root / "runtime"
            _write_config(state, ("fam.ask",))
            service = LocalProductService(ProductServiceSettings(
                state, runtime, console_port=0,
            ), _Runtime(), context_profile_observer=ContextProfileFixture())
            service.start()
            client = None
            try:
                client = UnixMcpIngressClient.connect(
                    runtime / "mcp-ingress.sock", "editor-client",
                )
                tools = await client.list_tools()
                self.assertEqual(("fam.ask",), tuple(
                    item.capability_id for item in tools
                ))
                outcome = await client.call_tool(
                    tools[0].name, {"prompt": "Explain the durable lifecycle."},
                )
                self.assertFalse(outcome.is_error)
                self.assertEqual(
                    "MCP entered durable FAM Core",
                    outcome.structured_content["content"],
                )
                self.assertEqual(
                    "completed", outcome.structured_content["status"],
                )
                storage = service._storage_unit
                self.assertIsNotNone(storage)
                database = storage.result.database
                rows = database.fetchall(
                    "SELECT authority_ref FROM authority_grants "
                    "WHERE authority_ref LIKE 'authority-mcp-%'"
                )
                self.assertEqual(1, len(rows))
                grant = storage.core.repositories().authorities.get(rows[0][0])
                self.assertEqual("local-editor", grant.principal_id)
                with self.assertRaises(PermissionError):
                    UnixMcpIngressClient.connect(
                        runtime / "mcp-ingress.sock", "not-allowlisted",
                    )
            finally:
                if client is not None:
                    client.close()
                service.stop()
            self.assertFalse((runtime / "mcp-ingress.sock").exists())

    async def test_verified_tool_withholds_unverified_model_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state, runtime = root / "state", root / "runtime"
            _write_config(state, ("fam.ask.verified",))
            service = LocalProductService(ProductServiceSettings(
                state, runtime, console_port=0,
            ), _Runtime(), context_profile_observer=ContextProfileFixture())
            service.start()
            client = UnixMcpIngressClient.connect(
                runtime / "mcp-ingress.sock", "editor-client",
            )
            try:
                tool = (await client.list_tools())[0]
                outcome = await client.call_tool(tool.name, {"prompt": "Verify this."})
                self.assertTrue(outcome.is_error)
                self.assertEqual("withheld", outcome.structured_content["status"])
                self.assertIsNone(outcome.structured_content["content"])
            finally:
                client.close()
                service.stop()

    async def test_installed_cli_bridge_speaks_official_mcp_stdio(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state, runtime, prefix = root / "state", root / "runtime", root / "prefix"
            (prefix / "active").mkdir(parents=True)
            _write_config(state, ("fam.ask",))
            service = LocalProductService(ProductServiceSettings(
                state, runtime, console_port=0,
            ), _Runtime(), context_profile_observer=ContextProfileFixture())
            service.start()
            session = None
            try:
                session = await OfficialMcpStdioSession.open(McpStdioConfiguration(
                    Path(sys.executable).absolute(),
                    (
                        "-m", "fam_os.product.cli", "--prefix", str(prefix),
                        "mcp", "serve", "--client-id", "editor-client",
                        "--runtime-root", str(runtime),
                    ),
                    (("PYTHONPATH", str(Path.cwd() / "src")),),
                    Path.cwd(),
                ))
                server = await session.initialize()
                self.assertEqual("FAM_OS", server.name)
                page = await session.list_tools()
                self.assertEqual(1, len(page.items))
                result = await session.call_tool(
                    page.items[0].name, {"prompt": "Use the MCP bridge."},
                )
                self.assertFalse(result.is_error)
                self.assertEqual(
                    "MCP entered durable FAM Core",
                    result.structured_content["content"],
                )
            finally:
                if session is not None:
                    await session.close()
                service.stop()


def _write_config(state: Path, capabilities) -> None:
    path = state / "config/mcp-ingress.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "contract_version": "fam.product.mcp-ingress/v1alpha1",
        "enabled": True,
        "clients": [{
            "client_id": "editor-client", "principal_id": "local-editor",
            "capabilities": list(capabilities), "session_ttl_seconds": 3600,
        }],
    }), encoding="utf-8")
    os.chmod(path, 0o600)


if __name__ == "__main__":
    unittest.main()
