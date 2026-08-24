"""Authenticated Console routing for trusted peer inspection and controls."""

from urllib.parse import parse_qs, unquote, urlsplit

from fam_os.fabric import (
    PeerManagementOperation,
    PeerManagementRequest,
    RemoteContextSensitivity,
    RemotePrivacyPolicy,
)
from fam_os.console.tasks import task_document
from fam_os.console.peer_context_routes import handle_peer_context_post


def handle_peer_get(handler, path: str) -> bool:
    if not path.startswith("/api/v1/peers"):
        return False
    if handler._session() is None:
        handler.send_error(401)
        return True
    service = handler.server.peer_api
    if service is None:
        handler._json(503, {"error": "Trusted peer controls are unavailable."})
        return True
    try:
        if path == "/api/v1/peers":
            _collection(handler, "peers", service.trusted_peers())
        elif path == "/api/v1/peers/receipts":
            _collection(handler, "control_receipts", service.control_receipts())
        elif path == "/api/v1/peers/context-evidence":
            _collection(handler, "context_evidence", service.context_evidence())
        else:
            parts = path.strip("/").split("/")
            if len(parts) != 4:
                raise ValueError("peer path is invalid")
            handler._json(200, task_document(service.peer(unquote(parts[3]))))
    except KeyError:
        handler.send_error(404)
    except (TypeError, ValueError) as error:
        handler._json(400, {"error": str(error)})
    return True


def handle_peer_post(handler, path: str, document: dict) -> bool:
    if not path.startswith("/api/v1/peers/"):
        return False
    service = handler.server.peer_api
    if service is None:
        handler._json(503, {"error": "Trusted peer controls are unavailable."})
        return True
    if handle_peer_context_post(handler, path, document):
        return True
    parts = path.strip("/").split("/")
    if len(parts) != 5:
        raise ValueError("peer mutation path is invalid")
    enrollment_id, operation = unquote(parts[3]), parts[4]
    if operation == "probe":
        _exact(document, {"request_id"})
        request_id = _text(document.get("request_id"), "request_id")
        handler._json(200, task_document(service.probe(enrollment_id, request_id)))
        return True
    base = {"request_id", "expected_revision", "confirmed", "reason_code"}
    if operation == "revoke":
        _exact(document, base)
        control = PeerManagementRequest(
            _text(document.get("request_id"), "request_id"), service.owner_id,
            PeerManagementOperation.REVOKE, enrollment_id,
            _revision(document), _confirmed(document),
            _text(document.get("reason_code"), "reason_code"),
        )
    elif operation == "privacy":
        extra = {
            "maximum_context_bytes", "sensitivities", "purpose_ids",
            "workspace_ids", "raw_content_allowed",
        }
        _exact(document, base | extra)
        peer = service.peer(enrollment_id)
        policy = RemotePrivacyPolicy(
            service.owner_id, (peer.device_id,),
            _texts(document.get("purpose_ids"), "purpose_ids"),
            _texts(document.get("workspace_ids"), "workspace_ids"),
            _positive(document.get("maximum_context_bytes"), "maximum_context_bytes"),
            tuple(RemoteContextSensitivity(value) for value in _texts(
                document.get("sensitivities"), "sensitivities",
            )),
            _boolean(document.get("raw_content_allowed"), "raw_content_allowed"),
        )
        control = PeerManagementRequest(
            _text(document.get("request_id"), "request_id"), service.owner_id,
            PeerManagementOperation.SET_PRIVACY, enrollment_id,
            _revision(document), _confirmed(document),
            _text(document.get("reason_code"), "reason_code"), policy,
        )
    else:
        raise ValueError("peer mutation operation is invalid")
    handler._json(200, task_document(service.apply_control(control)))
    return True


def _collection(handler, name, values) -> None:
    offset, limit = _page(handler.path)
    handler._json(200, {
        "offset": offset, "total_count": len(values),
        name: [task_document(item) for item in values[offset:offset + limit]],
    })


def _page(raw: str) -> tuple[int, int]:
    query = parse_qs(urlsplit(raw).query, strict_parsing=True)
    if set(query) - {"offset", "limit"} or any(len(value) != 1 for value in query.values()):
        raise ValueError("peer page query is invalid")
    offset = int(query.get("offset", ["0"])[0])
    limit = int(query.get("limit", ["100"])[0])
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError("peer page is outside bounds")
    return offset, limit


def _exact(document, fields) -> None:
    if set(document) != fields:
        raise ValueError("peer control fields must match exactly")


def _text(value, name) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"peer {name} is required")
    return value


def _texts(value, name) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"peer {name} must be a nonempty text array")
    return tuple(value)


def _positive(value, name) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"peer {name} must be positive")
    return value


def _revision(document) -> int:
    value = document.get("expected_revision")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("peer expected_revision is invalid")
    return value


def _confirmed(document) -> bool:
    return _boolean(document.get("confirmed"), "confirmed")


def _boolean(value, name) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"peer {name} must be boolean")
    return value
