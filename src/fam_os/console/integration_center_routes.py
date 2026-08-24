"""Console routes for the owner-facing Integration Center."""

from urllib.parse import unquote


def handle_integration_center_get(handler, path: str) -> bool:
    if not path.startswith("/api/v1/integration-center"):
        return False
    api = handler.server.integration_center
    if api is None:
        handler._json(503, {"error": "integration center is unavailable"})
    elif path == "/api/v1/integration-center/catalog":
        handler._json(200, api.catalog())
    elif path == "/api/v1/integration-center/configured":
        handler._json(200, api.configured())
    else:
        return False
    return True


def handle_integration_center_post(handler, path: str, document: dict) -> bool:
    prefix = "/api/v1/integration-center/"
    if not path.startswith(prefix):
        return False
    api = handler.server.integration_center
    if api is None:
        handler._json(503, {"error": "integration center is unavailable"})
        return True
    remainder = unquote(path.removeprefix(prefix))
    if remainder.endswith("/configure"):
        handler._json(200, api.configure(remainder.removesuffix("/configure"), document))
    elif remainder.endswith("/test"):
        handler._json(200, api.test(remainder.removesuffix("/test")))
    else:
        return False
    return True
