import hashlib
import os
import tempfile
import threading
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fam_os.adapters.shell import (
    ShellRequestDispatcher,
    UnixShellClientConfiguration,
    UnixShellCoreClient,
    UnixShellServer,
    UnixShellServerConfiguration,
)
from fam_os.applications.transport.auth import PeerAuthorizationPolicy
from fam_os.memory import (
    MAX_MANAGED_DOCUMENT_BYTES,
    DocumentCorrectionRequest,
    DocumentManagementOperation,
    DocumentManagementReceipt,
    MemoryDocumentExport,
)
from fam_os.schemas import decode_document, encode_document
from fam_os.shell import (
    ShellMemoryOperation,
    ShellMemoryQuery,
    ShellMemoryResponse,
)
from fam_os.shell.wire import (
    ShellWireKind,
    decode_memory_response,
    encode_frame,
    memory_response_message,
    request_message,
)
from tests.contract.schema_manifest_fixtures import document_management_values


class ShellMemoryWireTests(unittest.TestCase):
    def test_query_and_response_are_strict_registered_roots(self):
        inspection, *_values, receipt = document_management_values()
        query = ShellMemoryQuery("list-1", ShellMemoryOperation.LIST, offset=20, limit=10)
        response = ShellMemoryResponse(
            "list-1", ShellMemoryOperation.LIST, 20, 21, documents=(inspection,),
        )
        self.assertEqual(query, decode_document(encode_document(query)))
        self.assertEqual(response, decode_document(encode_document(response)))
        message = memory_response_message("response-1", "request-1", response)
        self.assertEqual(response, decode_memory_response(message))
        self.assertEqual("correct", receipt.operation.value)

    def test_transport_carries_worst_case_bounded_correction(self):
        content = "\x01" * MAX_MANAGED_DOCUMENT_BYTES
        digest = hashlib.sha256(content.encode()).hexdigest()
        request = DocumentCorrectionRequest(
            "correction-1", "document-1", "a" * 64, content, digest, True,
        )
        frame = encode_frame(request_message(
            "message-1", ShellWireKind.MEMORY_CORRECT, request,
        ))
        self.assertGreater(len(frame), MAX_MANAGED_DOCUMENT_BYTES)


class ShellMemoryTransportTests(unittest.TestCase):
    def test_authenticated_endpoint_carries_every_memory_control(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = _private_socket_path(temporary)
            memory = _MemoryGateway()
            server = UnixShellServer(
                UnixShellServerConfiguration(path),
                PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(_UnusedCore(), memory, ids("response")),
            )
            server.open()
            self.addCleanup(server.close)
            client = UnixShellCoreClient(
                UnixShellClientConfiguration(path), ids("request"),
            )
            query = ShellMemoryQuery("list-1", ShellMemoryOperation.LIST)
            listed = serve(server, lambda: client.memory_query(query))
            self.assertEqual(1, listed.total_count)
            inspection = ShellMemoryQuery(
                "inspect-1", ShellMemoryOperation.INSPECT,
                memory.inspection.approval.document_id, limit=1,
            )
            self.assertEqual(memory.inspection.approval.document_id, serve(
                server, lambda: client.memory_query(inspection),
            ).documents[0].approval.document_id)
            exported = ShellMemoryQuery(
                "export-1", ShellMemoryOperation.EXPORT,
                memory.inspection.approval.document_id, limit=1,
            )
            self.assertEqual("content", serve(
                server, lambda: client.memory_query(exported),
            ).exported_document.content)
            receipt_query = ShellMemoryQuery("receipts-1", ShellMemoryOperation.RECEIPTS)
            self.assertEqual(1, len(serve(
                server, lambda: client.memory_query(receipt_query),
            ).receipts))
            correction, expiration, deletion = document_management_values()[1:4]
            self.assertEqual(ShellMemoryOperation.CORRECT, serve(
                server, lambda: client.memory_correct(correction),
            ).operation)
            self.assertEqual(ShellMemoryOperation.EXPIRE, serve(
                server, lambda: client.memory_expire(expiration),
            ).operation)
            self.assertEqual(ShellMemoryOperation.DELETE, serve(
                server, lambda: client.memory_delete(deletion),
            ).operation)

    def test_absent_management_service_returns_stable_content_free_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = _private_socket_path(temporary)
            server = UnixShellServer(
                UnixShellServerConfiguration(path),
                PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(_UnusedCore()),
            )
            server.open()
            self.addCleanup(server.close)
            client = UnixShellCoreClient(UnixShellClientConfiguration(path))
            query = ShellMemoryQuery("list-1", ShellMemoryOperation.LIST)
            with self.assertRaisesRegex(RuntimeError, "shell.memory_unavailable"):
                serve(server, lambda: client.memory_query(query))


class _MemoryGateway:
    def __init__(self):
        self.inspection = document_management_values()[0]
        self.correction_receipt = document_management_values()[4]

    def inspections(self):
        return (self.inspection,)

    def inspect(self, document_id):
        if document_id != self.inspection.approval.document_id:
            raise KeyError(document_id)
        return self.inspection

    def export(self, document_id):
        self.inspect(document_id)
        return MemoryDocumentExport(self.inspection.approval, "content", self.inspection.content_sha256)

    def receipts(self):
        return (self.correction_receipt,)

    def correct(self, request):
        return _receipt(request, DocumentManagementOperation.CORRECT, request.document_id)

    def expire(self, request):
        return _receipt(request, DocumentManagementOperation.EXPIRE, request.grant_id)

    def delete(self, request):
        return _receipt(request, DocumentManagementOperation.DELETE, request.document_id)


def _receipt(request, operation, target):
    resulting = request.replacement_content_sha256 if operation is DocumentManagementOperation.CORRECT else None
    return DocumentManagementReceipt(
        f"receipt-{request.request_id}", request.request_id, operation, target,
        "owner-1", "owner-1", datetime(2026, 7, 17, tzinfo=UTC),
        "a" * 64, resulting,
        (document_management_values()[0].approval.document_id,), "b" * 64,
        operation is not DocumentManagementOperation.CORRECT,
    )


class _UnusedCore:
    pass


def _private_socket_path(directory):
    root = Path(directory)
    os.chmod(root, 0o700)
    return root / "shell.sock"


def ids(prefix):
    values = iter(range(30))
    return lambda: f"{prefix}-{next(values)}"


def serve(server, operation):
    thread = threading.Thread(target=server.serve_once, daemon=True)
    thread.start()
    try:
        return operation()
    finally:
        thread.join(timeout=3)
        if thread.is_alive():
            raise AssertionError("Shell server did not complete")


if __name__ == "__main__":
    unittest.main()
