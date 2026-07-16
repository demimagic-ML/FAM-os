"""Local MCP client adapter behind Application Fabric contracts."""

from fam_os.adapters.mcp.client import McpClientAdapter, McpOperationOutcome
from fam_os.adapters.mcp.mapping import (
    McpCapabilityBinding, McpMappedConnector, McpPrimitiveKind, map_discovery,
)
from fam_os.adapters.mcp.lifecycle import McpConnectorLifecycle
from fam_os.adapters.mcp.policy import McpConnectorPolicy, McpToolPolicy
from fam_os.adapters.mcp.ports import McpClientSessionPort
from fam_os.adapters.mcp.sdk import McpStdioConfiguration, OfficialMcpStdioSession
from fam_os.adapters.mcp.types import (
    McpCallResult, McpDiscoverySnapshot, McpReadResult, McpResource,
    McpResourcePage, McpServerInfo, McpTool, McpToolPage,
)

__all__ = [
    "McpCallResult", "McpCapabilityBinding", "McpClientAdapter",
    "McpClientSessionPort", "McpConnectorPolicy", "McpDiscoverySnapshot",
    "McpConnectorLifecycle", "McpMappedConnector", "McpOperationOutcome", "McpPrimitiveKind",
    "McpReadResult", "McpResource", "McpResourcePage", "McpServerInfo",
    "McpStdioConfiguration", "McpTool", "McpToolPage", "McpToolPolicy",
    "OfficialMcpStdioSession", "map_discovery",
]
