"""Console routes for useful workflows and durable task history."""

from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlsplit


def handle_useful_get(handler, path: str) -> bool:
    if not path.startswith("/api/v1/useful/"):
        return False
    api = handler.server.useful_task_api
    if api is None:
        handler._json(503, {"error": "useful workflows are unavailable"})
        return True
    if path == "/api/v1/useful/workflows":
        handler._json(200, {"workflows": api.workflows()})
        return True
    if path == "/api/v1/useful/tasks":
        query = parse_qs(urlsplit(handler.path).query)
        handler._json(200, api.list(
            limit=_integer(query, "limit", 50), offset=_integer(query, "offset", 0),
            query=_optional(query, "q"), project_id=_optional(query, "project_id"),
            attention_only=_optional(query, "attention") == "true",
        ))
        return True
    artifact_prefix = "/api/v1/useful/artifacts/"
    if path.startswith(artifact_prefix):
        artifact_id = unquote(path.removeprefix(artifact_prefix))
        if not artifact_id or "/" in artifact_id:
            raise ValueError("useful artifact id is invalid")
        handler._json(200, api.artifact_document(artifact_id))
        return True
    prefix = "/api/v1/useful/tasks/"
    if path.startswith(prefix):
        remainder = unquote(path.removeprefix(prefix))
        timeline = remainder.endswith("/timeline")
        task_id = remainder.removesuffix("/timeline") if timeline else remainder
        if not task_id or "/" in task_id:
            raise ValueError("useful task id is invalid")
        handler._json(200, api.timeline(task_id) if timeline else api.inspect(task_id))
        return True
    return False


def handle_useful_post(handler, path: str, document: dict) -> bool:
    if not path.startswith("/api/v1/useful/"):
        return False
    api = handler.server.useful_task_api
    if api is None:
        handler._json(503, {"error": "useful workflows are unavailable"})
    elif path == "/api/v1/useful/tasks":
        handler._json(201, api.run(document))
    elif path.startswith("/api/v1/useful/tasks/") and path.endswith("/retry"):
        task_id = unquote(path.removeprefix("/api/v1/useful/tasks/").removesuffix("/retry"))
        handler._json(201, api.retry(task_id))
    elif path.startswith("/api/v1/useful/tasks/") and path.endswith("/fork"):
        task_id = unquote(path.removeprefix("/api/v1/useful/tasks/").removesuffix("/fork"))
        handler._json(201, api.fork(task_id, document))
    else:
        return False
    return True


def _integer(query, name: str, default: int) -> int:
    values = query.get(name)
    if values is None:
        return default
    if len(values) != 1:
        raise ValueError("query parameter must occur once")
    return int(values[0])


def _optional(query, name: str) -> str | None:
    values = query.get(name)
    if values is None:
        return None
    if len(values) != 1:
        raise ValueError("query parameter must occur once")
    return values[0]
