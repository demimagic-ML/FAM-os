"""Console routes for saved and triggered user automations."""

from urllib.parse import unquote


def handle_automation_get(handler, path: str) -> bool:
    if not path.startswith("/api/v1/automations") and path != "/api/v1/notifications":
        return False
    api = handler.server.automation_service
    if api is None:
        handler._json(503, {"error": "automations are unavailable"})
    elif path == "/api/v1/automations":
        handler._json(200, api.list())
    elif path == "/api/v1/notifications":
        handler._json(200, api.notifications())
    elif path.startswith("/api/v1/automations/") and path.endswith("/runs"):
        identifier = unquote(path.removeprefix("/api/v1/automations/").removesuffix("/runs"))
        handler._json(200, api.runs(identifier))
    else:
        return False
    return True


def handle_automation_post(handler, path: str, document: dict) -> bool:
    if not path.startswith("/api/v1/automations"):
        return False
    api = handler.server.automation_service
    if api is None:
        handler._json(503, {"error": "automations are unavailable"})
    elif path == "/api/v1/automations":
        handler._json(201, api.create(document))
    elif path.startswith("/api/v1/automations/") and path.endswith("/run"):
        identifier = unquote(path.removeprefix("/api/v1/automations/").removesuffix("/run"))
        handler._json(200, api.run_now(identifier))
    elif path.startswith("/api/v1/automations/") and path.endswith("/webhook"):
        identifier = unquote(path.removeprefix("/api/v1/automations/").removesuffix("/webhook"))
        handler._json(200, api.webhook(identifier, document))
    else:
        return False
    return True
