import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fam_os.memory import DocumentManagementOperation, DocumentManagementReceipt, MemoryDocumentExport
from fam_os.shell import (
    ShellController,
    ShellMemoryOperation,
    ShellMemoryResponse,
    TerminalShell,
)
from tests.contract.schema_manifest_fixtures import document_management_values


class ShellMemoryTerminalTests(unittest.TestCase):
    def test_terminal_lists_inspects_exports_and_pages_receipts(self):
        client = _MemoryClient()
        shell = TerminalShell(ShellController(client, request_id_factory=ids()))
        document_id = client.inspection.approval.document_id
        listed, _ = shell.execute("/memory list 0 25")
        self.assertIn("Persistent memory: 1 shown of 1", listed)
        self.assertIn(document_id, listed)
        inspected, _ = shell.execute(f"/memory inspect {document_id}")
        self.assertIn("Digest:", inspected)
        exported, _ = shell.execute(f"/memory export {document_id}")
        self.assertIn("Persistent memory export:", exported)
        self.assertIn("content", exported)
        receipts, _ = shell.execute("/memory receipts 0 10")
        self.assertIn("Memory receipts: 1 shown of 1", receipts)

    def test_mutations_require_literal_confirmation_and_read_bounded_utf8(self):
        client = _MemoryClient()
        shell = TerminalShell(ShellController(client, request_id_factory=ids()))
        inspection = client.inspection
        document_id = inspection.approval.document_id
        digest = inspection.content_sha256
        denied, _ = shell.execute(f"/memory delete {document_id} {digest}")
        self.assertEqual("Command could not be completed safely.", denied)
        with tempfile.TemporaryDirectory() as temporary:
            replacement = Path(temporary) / "replacement.txt"
            replacement.write_text("corrected content", encoding="utf-8")
            corrected, _ = shell.execute(
                f"/memory correct {document_id} {digest} {replacement} --confirm"
            )
            self.assertIn("Memory correct completed.", corrected)
            link = Path(temporary) / "replacement-link.txt"
            link.symlink_to(replacement)
            rejected, _ = shell.execute(
                f"/memory correct {document_id} {digest} {link} --confirm"
            )
            self.assertEqual("Command could not be completed safely.", rejected)
        deleted, _ = shell.execute(
            f"/memory delete {document_id} {digest} --confirm"
        )
        self.assertIn("Payload removed: yes", deleted)
        expired, _ = shell.execute("/memory expire grant-1 --confirm")
        self.assertIn("Memory expire completed.", expired)
        self.assertEqual(["correct", "delete", "expire"], client.mutations)

    def test_safe_memory_errors_explain_recovery_without_provider_detail(self):
        shell = TerminalShell(ShellController(_UnavailableMemoryClient()))
        output, _ = shell.execute("/memory list")
        self.assertEqual("Persistent memory management is unavailable.", output)
        self.assertNotIn("secret", output)


class _MemoryClient:
    def __init__(self):
        self.inspection = document_management_values()[0]
        self.history = document_management_values()[4]
        self.mutations = []

    def memory_query(self, query):
        if query.operation is ShellMemoryOperation.LIST:
            return ShellMemoryResponse(
                query.request_id, query.operation, query.offset, 1,
                documents=(self.inspection,),
            )
        if query.operation is ShellMemoryOperation.INSPECT:
            return ShellMemoryResponse(
                query.request_id, query.operation, total_count=1,
                documents=(self.inspection,),
            )
        if query.operation is ShellMemoryOperation.EXPORT:
            value = MemoryDocumentExport(
                self.inspection.approval, "content", self.inspection.content_sha256,
            )
            return ShellMemoryResponse(
                query.request_id, query.operation, total_count=1,
                exported_document=value,
            )
        return ShellMemoryResponse(
            query.request_id, query.operation, query.offset, 1,
            receipts=(self.history,),
        )

    def memory_correct(self, request):
        self.mutations.append("correct")
        return self._mutation(request, DocumentManagementOperation.CORRECT)

    def memory_delete(self, request):
        self.mutations.append("delete")
        return self._mutation(request, DocumentManagementOperation.DELETE)

    def memory_expire(self, request):
        self.mutations.append("expire")
        return self._mutation(request, DocumentManagementOperation.EXPIRE)

    def _mutation(self, request, operation):
        target = getattr(request, "document_id", None) or request.grant_id
        resulting = getattr(request, "replacement_content_sha256", None)
        receipt = DocumentManagementReceipt(
            f"receipt-{request.request_id}", request.request_id, operation, target,
            "owner-1", "owner-1", datetime(2026, 7, 17, tzinfo=UTC),
            self.inspection.content_sha256, resulting,
            (self.inspection.approval.document_id,),
            "b" * 64, operation is not DocumentManagementOperation.CORRECT,
        )
        response_operation = ShellMemoryOperation(operation.value)
        return ShellMemoryResponse(
            request.request_id, response_operation, total_count=1, receipt=receipt,
        )


class _UnavailableMemoryClient:
    def memory_query(self, _query):
        raise RuntimeError("shell.memory_unavailable")


def ids():
    values = iter(range(50))
    return lambda: f"memory-request-{next(values)}"


if __name__ == "__main__":
    unittest.main()
