"""Bounded presentation contracts for persistent memory management in Shell."""

from dataclasses import dataclass
from enum import StrEnum

from fam_os.memory import (
    DocumentInspection,
    DocumentManagementOperation,
    DocumentManagementReceipt,
    MemoryDocumentExport,
)

SHELL_MEMORY_CONTRACT_VERSION = "fam.shell.memory/v1alpha1"
MAX_SHELL_MEMORY_PAGE = 200


class ShellMemoryOperation(StrEnum):
    LIST = "list"
    INSPECT = "inspect"
    EXPORT = "export"
    CORRECT = "correct"
    EXPIRE = "expire"
    DELETE = "delete"
    RECEIPTS = "receipts"


@dataclass(frozen=True, slots=True)
class ShellMemoryQuery:
    request_id: str
    operation: ShellMemoryOperation
    target_id: str | None = None
    offset: int = 0
    limit: int = 100
    contract_version: str = SHELL_MEMORY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        if not isinstance(self.operation, ShellMemoryOperation) or self.operation not in {
            ShellMemoryOperation.LIST, ShellMemoryOperation.INSPECT,
            ShellMemoryOperation.EXPORT, ShellMemoryOperation.RECEIPTS,
        }:
            raise ValueError("Shell memory query operation is invalid")
        targeted = self.operation in {
            ShellMemoryOperation.INSPECT, ShellMemoryOperation.EXPORT,
        }
        if targeted != (self.target_id is not None):
            raise ValueError("Shell memory query target is invalid")
        if self.target_id is not None:
            _text(self.target_id, "target_id")
        if isinstance(self.offset, bool) or self.offset < 0:
            raise ValueError("Shell memory query offset is invalid")
        if isinstance(self.limit, bool) or not 1 <= self.limit <= MAX_SHELL_MEMORY_PAGE:
            raise ValueError("Shell memory query limit is invalid")
        if targeted and (self.offset != 0 or self.limit != 1):
            raise ValueError("targeted Shell memory queries require one result")
        if self.contract_version != SHELL_MEMORY_CONTRACT_VERSION:
            raise ValueError("unsupported Shell memory contract version")


@dataclass(frozen=True, slots=True)
class ShellMemoryResponse:
    request_id: str
    operation: ShellMemoryOperation
    offset: int = 0
    total_count: int = 0
    documents: tuple[DocumentInspection, ...] = ()
    exported_document: MemoryDocumentExport | None = None
    receipt: DocumentManagementReceipt | None = None
    receipts: tuple[DocumentManagementReceipt, ...] = ()
    contract_version: str = SHELL_MEMORY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        if not isinstance(self.operation, ShellMemoryOperation):
            raise ValueError("Shell memory response operation is invalid")
        if isinstance(self.offset, bool) or self.offset < 0:
            raise ValueError("Shell memory response offset is invalid")
        if isinstance(self.total_count, bool) or self.total_count < 0:
            raise ValueError("Shell memory response count is invalid")
        if len(self.documents) > MAX_SHELL_MEMORY_PAGE:
            raise ValueError("Shell memory document page exceeds limit")
        if len(self.receipts) > MAX_SHELL_MEMORY_PAGE:
            raise ValueError("Shell memory receipt page exceeds limit")
        if any(not isinstance(item, DocumentInspection) for item in self.documents):
            raise ValueError("Shell memory documents are invalid")
        if any(not isinstance(item, DocumentManagementReceipt) for item in self.receipts):
            raise ValueError("Shell memory receipts are invalid")
        self._validate_shape()
        if self.contract_version != SHELL_MEMORY_CONTRACT_VERSION:
            raise ValueError("unsupported Shell memory contract version")

    def _validate_shape(self) -> None:
        populated = (
            bool(self.documents), self.exported_document is not None,
            self.receipt is not None, bool(self.receipts),
        )
        if self.operation is ShellMemoryOperation.LIST:
            valid = not any(populated[1:]) and self.total_count >= len(self.documents)
        elif self.operation is ShellMemoryOperation.INSPECT:
            valid = (
                len(self.documents) == 1 and not any(populated[1:])
                and self.offset == 0 and self.total_count == 1
            )
        elif self.operation is ShellMemoryOperation.EXPORT:
            valid = (
                populated == (False, True, False, False)
                and self.offset == 0 and self.total_count == 1
            )
        elif self.operation is ShellMemoryOperation.RECEIPTS:
            valid = not any(populated[:3]) and self.total_count >= len(self.receipts)
        else:
            valid = (
                populated == (False, False, True, False)
                and self.offset == 0 and self.total_count == 1
            )
        if not valid:
            raise ValueError("Shell memory response shape does not match operation")
        self._validate_receipt()

    def _validate_receipt(self) -> None:
        if self.receipt is None:
            return
        expected = {
            ShellMemoryOperation.CORRECT: DocumentManagementOperation.CORRECT,
            ShellMemoryOperation.EXPIRE: DocumentManagementOperation.EXPIRE,
            ShellMemoryOperation.DELETE: DocumentManagementOperation.DELETE,
        }.get(self.operation)
        if self.receipt.request_id != self.request_id or self.receipt.operation is not expected:
            raise ValueError("Shell memory receipt does not match response")


def _text(value, name) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{name} must be strict nonempty text")
    return value.strip()
