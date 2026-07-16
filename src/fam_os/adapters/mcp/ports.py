"""Provider port isolating the MCP SDK and transport lifecycle."""

from typing import Protocol

from fam_os.adapters.mcp.types import (
    McpCallResult, McpReadResult, McpResourcePage, McpServerInfo, McpToolPage,
)


class McpClientSessionPort(Protocol):
    async def initialize(self) -> McpServerInfo: ...

    async def list_resources(self, cursor: str | None = None) -> McpResourcePage: ...

    async def list_tools(self, cursor: str | None = None) -> McpToolPage: ...

    async def read_resource(self, uri: str) -> McpReadResult: ...

    async def call_tool(self, name: str, arguments: dict) -> McpCallResult: ...

    async def close(self) -> None: ...
