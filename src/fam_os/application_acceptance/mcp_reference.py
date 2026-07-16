"""Official-SDK MCP observation used by the acceptance composition."""

import asyncio
import sys
from pathlib import Path

from fam_os.adapters.mcp import (
    McpClientAdapter, McpConnectorPolicy, McpStdioConfiguration,
    McpToolPolicy, OfficialMcpStdioSession,
)
from fam_os.applications import (
    ApplicationAuthority, ApplicationIdentity, CapabilityKind,
)


def observe_reference_server(root: Path):
    return asyncio.run(_observe(root))


async def _observe(root):
    session = await OfficialMcpStdioSession.open(McpStdioConfiguration(
        Path(sys.executable),
        (str(root / "tests/fixtures/mcp_reference_server.py"),),
        working_directory=root,
    ))
    adapter = McpClientAdapter(session, _policy())
    try:
        mapped = await adapter.initialize()
        binding = next(
            item for item in mapped.bindings
            if item.primitive_name == "fam-test://document"
        )
        outcome = await adapter.observe(binding.entry.capability_id, {})
        if not outcome.succeeded:
            raise RuntimeError("MCP reference observation failed")
        return {
            "capability_id": binding.entry.capability_id,
            "connector_id": mapped.registration.connector_id,
            "payload": dict(outcome.payload),
        }
    finally:
        await adapter.close()


def _policy():
    return McpConnectorPolicy(
        "acceptance-reference", "acceptance-mcp", "acceptance-mcp-instance",
        ApplicationIdentity("app.acceptance-mcp", "Acceptance MCP reference"),
        ("fam-test://document",),
        (McpToolPolicy(
            "lookup", CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
        ),),
        expected_server_name="FAM MCP reference",
    )
