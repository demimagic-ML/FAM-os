"""Authenticated metadata-only Console controls for engineering secrets."""

from urllib.parse import unquote


_PREFIX = "/api/v1/engineering/secrets"


def handle_engineering_secret_get(handler, path: str) -> bool:
    if not _matches(path): return False
    if handler._session() is None:
        handler.send_error(401); return True
    api = handler.server.engineering_secret_api
    if api is None:
        handler._json(503, {"error": "Engineering secrets are unavailable."}); return True
    try:
        secret_ref, operation = _path(path)
        if secret_ref is None:
            document = {"secrets": list(api.list())}
        elif operation == "audit":
            document = api.audit(secret_ref)
        else:
            document = api.inspect(secret_ref)
    except KeyError:
        handler.send_error(404); return True
    except (TypeError, ValueError) as error:
        handler._json(400, {"error": str(error)}); return True
    handler._json(200, document)
    return True


def handle_engineering_secret_post(handler, path, document, session_id) -> bool:
    if not _matches(path): return False
    api = handler.server.engineering_secret_api
    if api is None:
        handler._json(503, {"error": "Engineering secrets are unavailable."}); return True
    secret_ref, operation = _path(path)
    if operation == "provision" and secret_ref is None:
        result = api.provision(document, session_id)
    elif secret_ref is not None and operation in {"rotate", "delete"}:
        if document.get("secret_ref") != secret_ref:
            raise PermissionError("engineering secret path and payload differ")
        result = api.rotate(document, session_id) if operation == "rotate" else api.delete(document, session_id)
    else:
        raise ValueError("engineering secret mutation path is invalid")
    handler._json(200, result)
    return True


def _path(path):
    parts = path.strip("/").split("/")
    prefix = ["api", "v1", "engineering", "secrets"]
    if parts[:4] != prefix or len(parts) not in {4, 5, 6}:
        raise ValueError("engineering secret path is invalid")
    if len(parts) == 4: return None, "list"
    if len(parts) == 5 and parts[4] == "provision": return None, "provision"
    secret_ref = unquote(parts[4])
    if not secret_ref.strip() or "/" in secret_ref:
        raise ValueError("engineering secret reference is invalid")
    operation = "inspect" if len(parts) == 5 else parts[5]
    if operation not in {"inspect", "audit", "rotate", "delete"}:
        raise ValueError("engineering secret operation is invalid")
    return secret_ref, operation


def _matches(path):
    return path == _PREFIX or path.startswith(_PREFIX + "/")
