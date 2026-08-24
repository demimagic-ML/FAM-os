"""Authenticated Console controls for persistent integration environments."""

import json
from urllib.parse import unquote

from fam_os.core.engineering import CandidateWorkspace, IntegrationEnvironmentPlan
from fam_os.schemas import encode_document, loads_document


_PREFIX = "/api/v1/engineering/environments"


def handle_integration_environment_get(handler, path: str) -> bool:
    if not _matches(path):
        return False
    if handler._session() is None:
        handler.send_error(401)
        return True
    api = handler.server.integration_environment_api
    if api is None:
        handler._json(503, {"error": "Integration environments are unavailable."})
        return True
    try:
        environment_id, operation = _path(path)
        if environment_id is None:
            values = api.active(api.owner_id)
            document = {"environments": [_stored(item) for item in values]}
        elif operation == "audit":
            values = api.receipts(api.owner_id, environment_id)
            document = {
                "environment_id": environment_id,
                "receipts": [encode_document(item) for item in values],
            }
        else:
            document = _stored(api.inspect(api.owner_id, environment_id))
    except KeyError:
        handler.send_error(404)
        return True
    except PermissionError as error:
        handler._json(403, {"error": str(error)})
        return True
    except (TypeError, ValueError) as error:
        handler._json(400, {"error": str(error)})
        return True
    handler._json(200, document)
    return True


def handle_integration_environment_post(
    handler, path: str, document: dict, session_id: str,
) -> bool:
    if not _matches(path):
        return False
    api = handler.server.integration_environment_api
    if api is None:
        handler._json(503, {"error": "Integration environments are unavailable."})
        return True
    environment_id, operation = _path(path)
    if operation == "start":
        _exact(document, {
            "owner_id", "plan", "candidate", "grant_id", "principal_id",
            "confirmed",
        })
        _confirmed(document)
        result = api.start(
            _text(document["owner_id"]),
            _contract(document["plan"], IntegrationEnvironmentPlan),
            _contract(document["candidate"], CandidateWorkspace),
            _text(document["grant_id"]), _text(document["principal_id"]),
            session_id, lambda: False,
        )
        response = encode_document(result)
    elif operation in {"cleanup", "reconcile"} and environment_id is not None:
        _exact(document, {"owner_id", "confirmed"})
        _confirmed(document)
        method = api.cleanup if operation == "cleanup" else api.reconcile
        response = encode_document(method(_text(document["owner_id"]), environment_id))
    else:
        raise ValueError("integration environment mutation path is invalid")
    handler._json(200, response)
    return True


def _path(path: str) -> tuple[str | None, str]:
    parts = path.strip("/").split("/")
    prefix = ["api", "v1", "engineering", "environments"]
    if parts[:4] != prefix or len(parts) not in {4, 5, 6}:
        raise ValueError("integration environment path is invalid")
    if len(parts) == 4:
        return None, "list"
    if len(parts) == 5 and parts[4] == "start":
        return None, "start"
    identity = unquote(parts[4])
    if not identity.strip() or "/" in identity:
        raise ValueError("integration environment identifier is invalid")
    operation = "inspect" if len(parts) == 5 else parts[5]
    if operation not in {"inspect", "audit", "cleanup", "reconcile"}:
        raise ValueError("integration environment operation is invalid")
    return identity, operation


def _matches(path: str) -> bool:
    return path == _PREFIX or path.startswith(_PREFIX + "/")


def _stored(value) -> dict:
    return {
        "state": value.state,
        "plan": encode_document(value.plan),
        "candidate": encode_document(value.candidate),
        "start_result": encode_document(value.start_result),
        "latest_receipt": encode_document(value.latest_receipt),
    }


def _contract(value, expected):
    if not isinstance(value, dict):
        raise ValueError("integration environment contract must be a schema envelope")
    decoded = loads_document(json.dumps(value, separators=(",", ":")))
    if not isinstance(decoded, expected):
        raise ValueError("integration environment schema type is invalid")
    return decoded


def _exact(document, expected) -> None:
    if set(document) != expected:
        raise ValueError("integration environment fields must match exactly")


def _confirmed(document) -> None:
    if document["confirmed"] is not True:
        raise PermissionError("integration environment action requires confirmation")


def _text(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("integration environment field must be non-empty text")
    return value
