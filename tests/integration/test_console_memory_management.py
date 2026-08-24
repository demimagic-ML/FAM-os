import hashlib
import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider
from fam_os.memory import (
    DocumentIndexApproval,
    DocumentInspection,
    DocumentManagementOperation,
    DocumentManagementReceipt,
    MemoryDocumentExport,
    MemoryScope,
)


CONTENT = "The retained project note."
DIGEST = hashlib.sha256(CONTENT.encode()).hexdigest()


class _Management:
    def __init__(self):
        now = datetime(2026, 7, 17, tzinfo=UTC)
        self.approval = DocumentIndexApproval(
            "document-1", "/home/user/project/README.md", DIGEST,
            MemoryScope("owner-1", ("project",), ("fam.shell",)),
            "owner-1", now, "nomic-embed-text", "a" * 64,
            grant_id="grant-1", expires_at=now + timedelta(days=7),
        )
        self.inspection = DocumentInspection(self.approval, 2, len(CONTENT), DIGEST)
        self.calls = []

    def inspections(self):
        return (self.inspection,)

    def inspect(self, document_id):
        self.calls.append(("inspect", document_id))
        if document_id != "document-1":
            raise KeyError(document_id)
        return self.inspection

    def export(self, document_id):
        self.calls.append(("export", document_id))
        return MemoryDocumentExport(self.approval, CONTENT, DIGEST)

    def correct(self, request):
        self.calls.append(("correct", request))
        return _receipt(
            request.request_id, DocumentManagementOperation.CORRECT,
            request.document_id, request.replacement_content_sha256, False,
        )

    def delete(self, request):
        self.calls.append(("delete", request))
        return _receipt(
            request.request_id, DocumentManagementOperation.DELETE,
            request.document_id, None, True,
        )

    def expire(self, request):
        self.calls.append(("expire", request))
        return _receipt(
            request.request_id, DocumentManagementOperation.EXPIRE,
            request.grant_id, None, True,
        )

    def receipts(self):
        return (_receipt(
            "history-request", DocumentManagementOperation.DELETE,
            "document-1", None, True,
        ),)


class _Indexes:
    def __init__(self):
        self.management = _Management()


class ConsoleMemoryManagementTests(unittest.TestCase):
    def test_owner_can_inspect_export_correct_delete_expire_and_read_receipts(self):
        with _running_console() as (base, opener, csrf, indexes):
            documents = _get(opener, base + "/api/v1/memory/documents")
            self.assertEqual("document-1", documents["documents"][0]["approval"]["document_id"])
            inspection = _get(opener, base + "/api/v1/memory/documents/document-1")
            self.assertEqual(DIGEST, inspection["content_sha256"])
            exported = _get(
                opener, base + "/api/v1/memory/documents/document-1/export",
            )
            self.assertEqual(CONTENT, exported["content"])

            replacement = "Corrected retained note."
            replacement_digest = hashlib.sha256(replacement.encode()).hexdigest()
            corrected = _post(opener, base, csrf, "/api/v1/memory/documents/document-1/correct", {
                "request_id": "correct-request", "expected_content_sha256": DIGEST,
                "replacement_content": replacement,
                "replacement_content_sha256": replacement_digest, "confirmed": True,
            })
            self.assertEqual("correct", corrected["operation"])
            deleted = _post(opener, base, csrf, "/api/v1/memory/documents/document-1/delete", {
                "request_id": "delete-request", "expected_content_sha256": DIGEST,
                "confirmed": True,
            })
            self.assertTrue(deleted["payload_removed"])
            expired = _post(opener, base, csrf, "/api/v1/memory/grants/grant-1/expire", {
                "request_id": "expire-request", "confirmed": True,
            })
            self.assertEqual("grant-1", expired["target_id"])
            history = _get(opener, base + "/api/v1/memory/receipts")
            self.assertEqual("delete", history["receipts"][0]["operation"])
            self.assertEqual(
                ["inspect", "export", "correct", "delete", "expire"],
                [call[0] for call in indexes.management.calls],
            )

    def test_management_denies_missing_session_confirmation_and_unknown_fields(self):
        with _running_console() as (base, opener, csrf, _indexes):
            with self.assertRaises(urllib.error.HTTPError) as unauthenticated:
                urllib.request.urlopen(base + "/api/v1/memory/documents")
            self.assertEqual(401, unauthenticated.exception.code)
            with self.assertRaises(urllib.error.HTTPError) as unconfirmed:
                _post(opener, base, csrf, "/api/v1/memory/documents/document-1/delete", {
                    "request_id": "delete-request", "expected_content_sha256": DIGEST,
                    "confirmed": False,
                })
            self.assertEqual(403, unconfirmed.exception.code)
            with self.assertRaises(urllib.error.HTTPError) as unknown:
                _post(opener, base, csrf, "/api/v1/memory/grants/grant-1/expire", {
                    "request_id": "expire-request", "confirmed": True, "scope": "wider",
                })
            self.assertEqual(400, unknown.exception.code)

    def test_correction_accepts_the_document_contract_beyond_generic_task_limit(self):
        with _running_console() as (base, opener, csrf, indexes):
            replacement = "x" * 300_000
            replacement_digest = hashlib.sha256(replacement.encode()).hexdigest()
            response = _post(
                opener, base, csrf,
                "/api/v1/memory/documents/document-1/correct",
                {
                    "request_id": "large-correction",
                    "expected_content_sha256": DIGEST,
                    "replacement_content": replacement,
                    "replacement_content_sha256": replacement_digest,
                    "confirmed": True,
                },
            )
            self.assertEqual("correct", response["operation"])
            request = indexes.management.calls[-1][1]
            self.assertEqual(300_000, len(request.replacement_content))


def _receipt(request_id, operation, target, resulting_digest, removed):
    return DocumentManagementReceipt(
        f"receipt-{request_id}", request_id, operation, target,
        "owner-1", "owner-1", datetime(2026, 7, 17, tzinfo=UTC),
        DIGEST, resulting_digest, ("document-1",), "b" * 64, removed,
    )


class _running_console:
    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory()
        indexes = _Indexes()
        self.server = ConsoleHttpServer(
            ("127.0.0.1", 0), LocalConsoleProvider(Path(self.temporary.name)),
            "x" * 32, memory_api=indexes,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        base = f"http://127.0.0.1:{self.server.server_port}"
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        )
        exchange = urllib.request.Request(
            base + "/api/v1/session", data=b"{}", method="POST",
            headers={"Authorization": "Bearer " + "x" * 32, "Origin": base},
        )
        session = json.loads(opener.open(exchange).read())
        return base, opener, session["csrf_token"], indexes

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()


def _get(opener, url):
    return json.loads(opener.open(url).read())


def _post(opener, base, csrf, path, document):
    request = urllib.request.Request(
        base + path, data=json.dumps(document).encode(), method="POST",
        headers={
            "Content-Type": "application/json", "Origin": base,
            "X-CSRF-Token": csrf,
        },
    )
    return json.loads(opener.open(request).read())


if __name__ == "__main__":
    unittest.main()
