"""Authenticated Console routes for durable engineering goals."""

from urllib.parse import parse_qs, urlsplit

from fam_os.core.agent import AgentAuthorityProfile
from fam_os.console.goal_events import stream_goal_events


_PREFIX = "/api/v1/goals"


def handle_goal_get(handler, path: str) -> bool:
    if path != _PREFIX and not path.startswith(_PREFIX + "/"):
        return False
    session = handler._session()
    if session is None:
        handler.send_error(401)
        return True
    service = handler.server.goal_mode_service
    if service is None:
        handler._json(503, {"error": "Goal Mode is unavailable."})
        return True
    if path == _PREFIX:
        query = parse_qs(urlsplit(handler.path).query)
        workspace = query.get("workspace_root", [None])[0]
        handler._json(200, service.list(service.owner_id, workspace_root=workspace))
        return True
    goal_id, operation = _parts(path)
    if operation == "events":
        stream_goal_events(handler, service, goal_id)
        return True
    if operation != "inspect":
        raise ValueError("goal read operation is invalid")
    try:
        handler._json(200, service.inspect(service.owner_id, goal_id))
    except KeyError:
        handler.send_error(404)
    return True


def handle_goal_post(handler, path: str, document: dict, session_id: str) -> bool:
    if path != _PREFIX and not path.startswith(_PREFIX + "/"):
        return False
    service = handler.server.goal_mode_service
    if service is None:
        handler._json(503, {"error": "Goal Mode is unavailable."})
        return True
    if path == _PREFIX:
        _exact(document, {"prompt", "workspace_root", "authority_profile"})
        response = service.prepare(
            service.owner_id, _text(document["prompt"]),
            _text(document["workspace_root"]),
            AgentAuthorityProfile(_text(document["authority_profile"])),
            session_id,
        )
        handler._json(201, response)
        return True
    goal_id, operation = _parts(path)
    if operation == "activate":
        _exact(document, {"confirmed"})
        response = service.activate(
            service.owner_id, goal_id, confirmed=document["confirmed"],
        )
    elif operation == "control":
        if set(document) not in ({"action"}, {"action", "content"}):
            raise ValueError("goal control fields are invalid")
        response = service.control(
            service.owner_id, goal_id, _text(document["action"]),
            str(document.get("content", "")),
        )
    else:
        raise ValueError("goal mutation operation is invalid")
    handler._json(202, response)
    return True


def _parts(path: str) -> tuple[str, str]:
    parts = path.strip("/").split("/")
    if len(parts) != 5 or parts[:3] != ["api", "v1", "goals"]:
        raise ValueError("goal path is invalid")
    return parts[3], parts[4]


def _text(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("goal text must not be empty")
    return value.strip()


def _exact(document: dict, keys: set[str]) -> None:
    if not isinstance(document, dict) or set(document) != keys:
        raise ValueError("goal request fields are invalid")
