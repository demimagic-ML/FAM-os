"""Official MCP Python SDK v1 stdio implementation of the provider port."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.mcp.types import (
    McpCallResult, McpReadResult, McpResource, McpResourcePage, McpServerInfo,
    McpTool, McpToolPage,
)


@dataclass(frozen=True, slots=True)
class McpStdioConfiguration:
    command: Path
    arguments: tuple[str, ...] = ()
    environment: tuple[tuple[str, str], ...] = ()
    working_directory: Path | None = None

    def __post_init__(self) -> None:
        if not self.command.is_absolute():
            raise ValueError("MCP stdio command must be absolute")
        if not self.command.is_file() or not os.access(self.command, os.X_OK):
            raise ValueError("MCP stdio command must be an executable file")
        if self.working_directory is not None and not self.working_directory.is_absolute():
            raise ValueError("MCP stdio working directory must be absolute")
        if self.working_directory is not None and not self.working_directory.is_dir():
            raise ValueError("MCP stdio working directory must be a directory")
        keys = tuple(key for key, _value in self.environment)
        if len(set(keys)) != len(keys) or any(not key or "=" in key for key in keys):
            raise ValueError("MCP stdio environment keys must be unique and non-empty")
        if any("\x00" in item for pair in self.environment for item in pair):
            raise ValueError("MCP stdio environment cannot contain null bytes")


class OfficialMcpStdioSession:
    def __init__(self, transport_context, session_context, session, error_stream):
        self._transport_context = transport_context
        self._session_context = session_context
        self._session = session
        self._error_stream = error_stream
        self._closed = False

    @classmethod
    async def open(cls, configuration: McpStdioConfiguration):
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as error:
            raise RuntimeError("MCP Python SDK v1 is not installed") from error
        parameters = StdioServerParameters(
            command=str(configuration.command),
            args=list(configuration.arguments),
            env=dict(configuration.environment) or None,
            cwd=configuration.working_directory,
        )
        error_stream = open(os.devnull, "w", encoding="utf-8")
        transport_context = stdio_client(parameters, errlog=error_stream)
        try:
            read_stream, write_stream = await transport_context.__aenter__()
            session_context = ClientSession(read_stream, write_stream)
            session = await session_context.__aenter__()
        except BaseException:
            await transport_context.__aexit__(*sys.exc_info())
            error_stream.close()
            raise
        return cls(transport_context, session_context, session, error_stream)

    async def initialize(self) -> McpServerInfo:
        result = await self._session.initialize()
        return McpServerInfo(
            result.serverInfo.name,
            result.serverInfo.version,
            str(result.protocolVersion),
        )

    async def list_resources(self, cursor=None) -> McpResourcePage:
        result = await self._session.list_resources(cursor=cursor)
        items = tuple(
            McpResource(
                str(item.uri), item.title or item.name,
                item.description, item.mimeType,
            )
            for item in result.resources
        )
        return McpResourcePage(items, result.nextCursor)

    async def list_tools(self, cursor=None) -> McpToolPage:
        result = await self._session.list_tools(cursor=cursor)
        items = tuple(_tool(item) for item in result.tools)
        return McpToolPage(items, result.nextCursor)

    async def read_resource(self, uri: str) -> McpReadResult:
        result = await self._session.read_resource(uri)
        contents = tuple(
            item.model_dump(mode="json", by_alias=True, exclude_none=True)
            for item in result.contents
        )
        return McpReadResult(contents)

    async def call_tool(self, name: str, arguments: dict) -> McpCallResult:
        result = await self._session.call_tool(name, arguments)
        content = tuple(
            item.model_dump(mode="json", by_alias=True, exclude_none=True)
            for item in result.content
        )
        return McpCallResult(result.isError, content, result.structuredContent)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._session_context.__aexit__(None, None, None)
            await self._transport_context.__aexit__(None, None, None)
        finally:
            self._error_stream.close()


def _tool(item):
    annotations = (
        item.annotations.model_dump(mode="json", by_alias=True, exclude_none=True)
        if item.annotations is not None else {}
    )
    return McpTool(
        item.name, item.description, item.inputSchema, item.outputSchema, annotations
    )
