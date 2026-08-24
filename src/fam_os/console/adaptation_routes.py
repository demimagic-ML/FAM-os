"""Authenticated Console routing for live adaptation inspection and control."""

from urllib.parse import parse_qs, unquote, urlsplit

from fam_os.adaptation import AdaptationControlOperation, LiveAdaptationControlRequest
from fam_os.console.tasks import task_document


def handle_adaptation_get(handler, path: str) -> bool:
    if not path.startswith("/api/v1/adaptation/"):
        return False
    if handler._session() is None:
        handler.send_error(401)
        return True
    adaptation = handler.server.adaptation_api
    if adaptation is None:
        handler._json(503, {"error": "Live adaptation controls are unavailable."})
        return True
    try:
        if path == "/api/v1/adaptation/status":
            handler._json(200, task_document(adaptation.control_state()))
        else:
            _collection(handler, adaptation, path)
    except (TypeError, ValueError) as error:
        handler._json(400, {"error": str(error)})
    return True


def handle_adaptation_post(handler, path: str, document: dict) -> bool:
    if not path.startswith("/api/v1/adaptation/"):
        return False
    adaptation = handler.server.adaptation_api
    if adaptation is None:
        handler._json(503, {"error": "Live adaptation controls are unavailable."})
        return True
    operation, workflow = _mutation_path(path)
    _exact_fields(document, {"request_id", "confirmed"})
    request_id = document.get("request_id")
    confirmed = document.get("confirmed")
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("adaptation request_id is required")
    if not isinstance(confirmed, bool):
        raise ValueError("adaptation confirmed must be boolean")
    receipt = adaptation.apply_control(LiveAdaptationControlRequest(
        request_id, operation, confirmed, workflow,
    ))
    handler._json(200, task_document(receipt))
    return True


def _collection(handler, adaptation, path: str) -> None:
    sources = {
        "/api/v1/adaptation/snapshots": ("snapshots", adaptation.snapshots),
        "/api/v1/adaptation/prewarms": ("prewarms", adaptation.receipts),
        "/api/v1/adaptation/health": ("health", adaptation.health),
        "/api/v1/adaptation/drift": ("drift_reports", adaptation.drift_reports),
        "/api/v1/adaptation/receipts": ("control_receipts", adaptation.control_receipts),
    }
    if path not in sources:
        raise ValueError("adaptation collection path is invalid")
    name, source = sources[path]
    values = source()
    offset, limit = _page(handler.path)
    page = values[offset:offset + limit]
    handler._json(200, {
        "offset": offset,
        "total_count": len(values),
        name: [task_document(item) for item in page],
    })


def _mutation_path(path: str):
    parts = path.strip("/").split("/")
    if len(parts) == 4 and parts[:3] == ["api", "v1", "adaptation"]:
        operation = AdaptationControlOperation(parts[3])
        if operation not in {
            AdaptationControlOperation.ENABLE,
            AdaptationControlOperation.DISABLE,
            AdaptationControlOperation.RESET,
        }:
            raise ValueError("adaptation mutation path is invalid")
        return operation, None
    if len(parts) == 6 and parts[:4] == ["api", "v1", "adaptation", "workflows"]:
        operation = AdaptationControlOperation(parts[5])
        if operation not in {
            AdaptationControlOperation.EVALUATE,
            AdaptationControlOperation.ROLLBACK,
        }:
            raise ValueError("adaptation workflow mutation is invalid")
        workflow = unquote(parts[4])
        if not workflow.strip():
            raise ValueError("adaptation workflow is required")
        return operation, workflow
    raise ValueError("adaptation mutation path is invalid")


def _page(raw_path: str) -> tuple[int, int]:
    query = parse_qs(urlsplit(raw_path).query, strict_parsing=True)
    if set(query) - {"offset", "limit"} or any(len(values) != 1 for values in query.values()):
        raise ValueError("adaptation page query is invalid")
    try:
        offset = int(query.get("offset", ["0"])[0])
        limit = int(query.get("limit", ["100"])[0])
    except ValueError as error:
        raise ValueError("adaptation page query must be numeric") from error
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError("adaptation page is outside bounds")
    return offset, limit


def _exact_fields(document: dict, expected: set[str]) -> None:
    if set(document) != expected:
        raise ValueError("adaptation control fields must match exactly")
