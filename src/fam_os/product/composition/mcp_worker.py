"""Single-task MCP client worker preserving official SDK context ownership."""

from __future__ import annotations

import asyncio
from concurrent.futures import Future
from dataclasses import dataclass
from queue import Queue
from threading import Thread

from fam_os.adapters.mcp.client import McpClientAdapter
from fam_os.adapters.mcp.sdk import McpStdioConfiguration, OfficialMcpStdioSession


@dataclass(frozen=True, slots=True)
class _Command:
    operation: str
    capability_id: str | None
    arguments: dict
    result: Future


class McpClientWorker:
    """Execute open, calls, and close in one persistent asyncio task."""

    def __init__(self, configuration: McpStdioConfiguration, policy) -> None:
        self._configuration = configuration
        self._policy = policy
        self._commands: Queue[_Command] = Queue()
        self._ready: Future = Future()
        self._thread = Thread(target=self._thread_main, name="fam-mcp-client", daemon=True)

    def start(self):
        self._thread.start()
        return self._ready.result(timeout=self._policy.operation_timeout_seconds + 5)

    def observe(self, capability_id: str, arguments: dict):
        return self._submit("observe", capability_id, arguments)

    def execute(self, capability_id: str, arguments: dict):
        return self._submit("execute", capability_id, arguments)

    def stop(self) -> None:
        if not self._thread.is_alive():
            return
        self._submit("stop", None, {})
        self._thread.join(timeout=self._policy.operation_timeout_seconds + 5)
        if self._thread.is_alive():
            raise TimeoutError("MCP client did not stop within its bound")

    def _submit(self, operation: str, capability_id: str | None, arguments: dict):
        result: Future = Future()
        self._commands.put(_Command(operation, capability_id, arguments, result))
        return result.result(timeout=self._policy.operation_timeout_seconds + 5)

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._serve())
        except BaseException as error:
            if not self._ready.done():
                self._ready.set_exception(error)

    async def _serve(self) -> None:
        session = await OfficialMcpStdioSession.open(self._configuration)
        client = McpClientAdapter(session, self._policy)
        try:
            mapped = await client.initialize()
            self._ready.set_result(mapped)
            while True:
                command = await asyncio.to_thread(self._commands.get)
                if command.operation == "stop":
                    command.result.set_result(None)
                    break
                try:
                    result = await self._invoke(client, command)
                except BaseException as error:
                    command.result.set_exception(error)
                else:
                    command.result.set_result(result)
        finally:
            await client.close()

    @staticmethod
    async def _invoke(client: McpClientAdapter, command: _Command):
        if command.capability_id is None:
            raise ValueError("MCP operation requires a capability")
        if command.operation == "observe":
            return await client.observe(command.capability_id, command.arguments)
        if command.operation == "execute":
            return await client.execute(command.capability_id, command.arguments)
        raise ValueError("unsupported MCP client operation")
