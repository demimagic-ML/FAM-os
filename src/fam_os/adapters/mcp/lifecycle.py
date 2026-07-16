"""Atomic registry lifecycle around one local MCP client adapter."""

from dataclasses import dataclass

from fam_os.adapters.mcp.client import McpClientAdapter
from fam_os.applications import CapabilityRegistry


@dataclass(slots=True)
class McpConnectorLifecycle:
    client: McpClientAdapter
    registry: CapabilityRegistry
    _connector_id: str | None = None

    async def start(self):
        if self._connector_id is not None:
            raise RuntimeError("MCP connector lifecycle is already started")
        try:
            mapped = await self.client.initialize()
            self.registry.register(mapped.registration)
        except BaseException:
            await self.client.close()
            raise
        self._connector_id = mapped.registration.connector_id
        return mapped.registration

    async def refresh(self):
        if self._connector_id is None:
            raise RuntimeError("MCP connector lifecycle is not started")
        try:
            mapped = await self.client.refresh()
            self.registry.register(mapped.registration)
        except BaseException:
            await self._retire()
            raise
        return mapped.registration

    async def stop(self) -> None:
        if self._connector_id is None:
            return
        await self._retire()

    async def _retire(self) -> None:
        connector_id = self._connector_id
        self._connector_id = None
        try:
            self.registry.unregister(connector_id)
        finally:
            await self.client.close()
