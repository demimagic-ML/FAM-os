import sys
import unittest
from pathlib import Path

try:
    import mcp  # noqa: F401
except ImportError:
    MCP_SDK_AVAILABLE = False
else:
    MCP_SDK_AVAILABLE = True

from fam_os.adapters.mcp import (
    McpClientAdapter, McpConnectorPolicy, McpStdioConfiguration,
    McpToolPolicy, OfficialMcpStdioSession,
)
from fam_os.applications import (
    ApplicationAuthority, ApplicationIdentity, CapabilityKind,
    ConfirmationPolicy, Reversibility,
)


ROOT = Path(__file__).parents[2]


@unittest.skipUnless(MCP_SDK_AVAILABLE, "official MCP SDK is not installed")
class OfficialMcpSdkIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_stdio_discovery_resource_and_tools(self):
        provider = await OfficialMcpStdioSession.open(McpStdioConfiguration(
            Path(sys.executable),
            (str(ROOT / "tests/fixtures/mcp_reference_server.py"),),
            working_directory=ROOT,
        ))
        adapter = McpClientAdapter(provider, _policy())
        try:
            mapped = await adapter.initialize()
            names = {item.primitive_name for item in mapped.bindings}
            self.assertEqual({"fam-test://document", "lookup", "replace"}, names)

            resource = _binding(mapped, "fam-test://document")
            lookup = _binding(mapped, "lookup")
            replace = _binding(mapped, "replace")
            observed = await adapter.observe(resource.entry.capability_id, {})
            searched = await adapter.observe(lookup.entry.capability_id, {"query": "fam"})
            changed = await adapter.execute(replace.entry.capability_id, {"text": "new"})
            self.assertTrue(observed.succeeded)
            self.assertTrue(searched.succeeded)
            self.assertEqual("FAM", searched.payload["structured_content"]["result"])
            self.assertTrue(changed.payload["structured_content"]["changed"])
        finally:
            await adapter.close()


def _policy():
    return McpConnectorPolicy(
        "reference", "connector-reference", "instance-reference",
        ApplicationIdentity("app.mcp-reference", "MCP reference"),
        ("fam-test://document",),
        (
            McpToolPolicy(
                "lookup", CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE
            ),
            McpToolPolicy(
                "replace", CapabilityKind.ACTION, ApplicationAuthority.MODIFY,
                Reversibility.REVERSIBLE, ConfirmationPolicy.ALWAYS,
                ("reference.changed",),
            ),
        ),
        expected_server_name="FAM MCP reference",
    )


def _binding(mapped, name):
    return next(item for item in mapped.bindings if item.primitive_name == name)


if __name__ == "__main__":
    unittest.main()
