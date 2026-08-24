"""Server-side mapping from Shell memory requests to the owner service."""

from fam_os.memory import (
    DocumentCorrectionRequest,
    DocumentDeletionRequest,
    DocumentExpirationRequest,
)
from fam_os.shell.memory_contracts import (
    ShellMemoryOperation,
    ShellMemoryQuery,
    ShellMemoryResponse,
)


def dispatch_memory(memory, command) -> ShellMemoryResponse:
    if memory is None:
        raise MemoryServiceUnavailable
    if isinstance(command, ShellMemoryQuery):
        return _query(memory, command)
    if isinstance(command, DocumentCorrectionRequest):
        return ShellMemoryResponse(
            command.request_id, ShellMemoryOperation.CORRECT,
            total_count=1, receipt=memory.correct(command),
        )
    if isinstance(command, DocumentExpirationRequest):
        return ShellMemoryResponse(
            command.request_id, ShellMemoryOperation.EXPIRE,
            total_count=1, receipt=memory.expire(command),
        )
    if isinstance(command, DocumentDeletionRequest):
        return ShellMemoryResponse(
            command.request_id, ShellMemoryOperation.DELETE,
            total_count=1, receipt=memory.delete(command),
        )
    raise ValueError("unsupported Shell memory request")


def _query(memory, command: ShellMemoryQuery) -> ShellMemoryResponse:
    if command.operation is ShellMemoryOperation.LIST:
        values = memory.inspections()
        return ShellMemoryResponse(
            command.request_id, command.operation, command.offset, len(values),
            documents=_page(values, command.offset, command.limit),
        )
    if command.operation is ShellMemoryOperation.RECEIPTS:
        values = memory.receipts()
        return ShellMemoryResponse(
            command.request_id, command.operation, command.offset, len(values),
            receipts=_page(values, command.offset, command.limit),
        )
    if command.operation is ShellMemoryOperation.INSPECT:
        value = memory.inspect(command.target_id)
        return ShellMemoryResponse(
            command.request_id, command.operation, total_count=1,
            documents=(value,),
        )
    if command.operation is ShellMemoryOperation.EXPORT:
        value = memory.export(command.target_id)
        return ShellMemoryResponse(
            command.request_id, command.operation, total_count=1,
            exported_document=value,
        )
    raise ValueError("unsupported Shell memory query")


def _page(values, offset: int, limit: int) -> tuple:
    return tuple(values[offset:offset + limit])


class MemoryServiceUnavailable(RuntimeError):
    """The installed service has no persistent memory management surface."""
