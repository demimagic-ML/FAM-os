"""Authenticated Console routes for owner engineering authority ceremonies."""

from urllib.parse import unquote


_PREFIX = "/api/v1/engineering/"


def handle_engineering_authority_get(handler, path: str) -> bool:
    if not path.startswith(_PREFIX):
        return False
    session = handler._session()
    if session is None:
        handler.send_error(401)
        return True
    authority = handler.server.engineering_authority_api
    if authority is None:
        handler._json(503, {"error": "Engineering authority is unavailable."})
        return True
    grant_id, operation = _grant_path(path)
    try:
        document = (
            authority.audit(grant_id)
            if operation == "audit"
            else authority.inspect(grant_id)
        )
    except KeyError:
        handler.send_error(404)
        return True
    except (TypeError, ValueError) as error:
        handler._json(400, {"error": str(error)})
        return True
    handler._json(200, document)
    return True


def handle_engineering_authority_post(
    handler, path: str, document: dict, session_id: str,
) -> bool:
    if not path.startswith(_PREFIX):
        return False
    authority = handler.server.engineering_authority_api
    if authority is None:
        handler._json(503, {"error": "Engineering authority is unavailable."})
        return True
    if path == _PREFIX + "authentication-contexts":
        result = authority.issue_context(document, session_id)
    elif path == _PREFIX + "grants/activate":
        result = authority.activate(document, session_id)
    else:
        grant_id, operation = _grant_path(path)
        if operation != "revoke":
            raise ValueError("engineering authority mutation path is invalid")
        result = authority.revoke(grant_id, document)
    handler._json(200, result)
    return True


def _grant_path(path: str) -> tuple[str, str]:
    parts = path.strip("/").split("/")
    if len(parts) not in {5, 6} or parts[:4] != ["api", "v1", "engineering", "grants"]:
        raise ValueError("engineering grant path is invalid")
    grant_id = unquote(parts[4])
    if not grant_id.strip() or "/" in grant_id:
        raise ValueError("engineering grant identifier is invalid")
    operation = "inspect" if len(parts) == 5 else parts[5]
    if operation not in {"inspect", "audit", "revoke"}:
        raise ValueError("engineering grant operation is invalid")
    return grant_id, operation
