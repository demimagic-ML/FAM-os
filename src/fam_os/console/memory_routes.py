"""Authenticated Console HTTP routing for persistent memory management."""

from __future__ import annotations

from uuid import uuid4

from fam_os.console.tasks import task_document
from fam_os.memory import (
    DocumentCorrectionRequest,
    DocumentDeletionRequest,
    DocumentExpirationRequest,
)


def handle_memory_get(handler, path: str) -> bool:
    if not path.startswith("/api/v1/memory/"):
        return False
    if handler._session() is None:
        handler.send_error(401)
        return True
    memory = handler.server.memory_api
    if memory is None:
        handler._json(503, {"error": "Persistent document indexing is unavailable."})
        return True
    try:
        if path == "/api/v1/memory/indexes":
            handler._json(200, {"indexes": memory.list()})
        else:
            _management_get(handler, path, memory.management)
    except KeyError:
        handler.send_error(404)
    except (TypeError, ValueError) as error:
        handler._json(400, {"error": str(error)})
    return True


def handle_memory_post(handler, path: str, document: dict) -> bool:
    if not path.startswith("/api/v1/memory/"):
        return False
    memory = handler.server.memory_api
    if memory is None:
        handler._json(503, {"error": "Persistent document indexing is unavailable."})
        return True
    if path == "/api/v1/memory/indexes":
        handler._json(200, task_document(memory.create(document)))
        return True
    management = memory.management
    if management is None:
        handler._json(503, {"error": "Persistent memory management is unavailable."})
        return True
    parts = path.strip("/").split("/")
    if len(parts) == 6 and parts[:4] == ["api", "v1", "memory", "documents"]:
        _document_mutation(handler, management, parts[4], parts[5], document)
        return True
    if len(parts) == 6 and parts[:4] == ["api", "v1", "memory", "grants"]:
        if parts[5] != "expire":
            return False
        _exact_fields(document, {"request_id", "confirmed"})
        receipt = management.expire(DocumentExpirationRequest(
            _request_id(document), parts[4], document.get("confirmed", False),
        ))
        handler._json(200, task_document(receipt))
        return True
    return False


def _management_get(handler, path: str, management) -> None:
    if management is None:
        handler._json(503, {"error": "Persistent memory management is unavailable."})
        return
    if path == "/api/v1/memory/documents":
        values = [task_document(item) for item in management.inspections()]
        handler._json(200, {"documents": values})
        return
    if path == "/api/v1/memory/receipts":
        values = [task_document(item) for item in management.receipts()]
        handler._json(200, {"receipts": values})
        return
    parts = path.strip("/").split("/")
    if len(parts) == 5 and parts[:4] == ["api", "v1", "memory", "documents"]:
        handler._json(200, task_document(management.inspect(parts[4])))
        return
    if (
        len(parts) == 6
        and parts[:4] == ["api", "v1", "memory", "documents"]
        and parts[5] == "export"
    ):
        handler._json(200, task_document(management.export(parts[4])))
        return
    handler.send_error(404)


def _document_mutation(handler, management, document_id, operation, document) -> None:
    if operation == "correct":
        _exact_fields(document, {
            "request_id", "expected_content_sha256", "replacement_content",
            "replacement_content_sha256", "confirmed",
        })
        correction = DocumentCorrectionRequest(
            _request_id(document), document_id, document["expected_content_sha256"],
            document["replacement_content"], document["replacement_content_sha256"],
            document.get("confirmed", False),
        )
        receipt = management.correct(correction)
    elif operation == "delete":
        _exact_fields(document, {
            "request_id", "expected_content_sha256", "confirmed",
        })
        deletion = DocumentDeletionRequest(
            _request_id(document), document_id, document["expected_content_sha256"],
            document.get("confirmed", False),
        )
        receipt = management.delete(deletion)
    else:
        raise KeyError("unknown document management operation")
    handler._json(200, task_document(receipt))


def _request_id(document: dict) -> str:
    value = document.get("request_id") or str(uuid4())
    if not isinstance(value, str):
        raise ValueError("memory management request_id must be text")
    return value


def _exact_fields(document: dict, fields: set[str]) -> None:
    if set(document) - fields:
        raise ValueError("unknown memory management request fields")
