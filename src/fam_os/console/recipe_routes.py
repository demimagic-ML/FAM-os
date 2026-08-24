"""Console routes for reusable workflow recipes."""

from urllib.parse import unquote


def handle_recipe_get(handler, path: str) -> bool:
    if path != "/api/v1/recipes":
        return False
    api = handler.server.recipe_library
    if api is None:
        handler._json(503, {"error": "workflow recipes are unavailable"})
    else:
        handler._json(200, api.list())
    return True


def handle_recipe_post(handler, path: str, document: dict) -> bool:
    if not path.startswith("/api/v1/recipes"):
        return False
    api = handler.server.recipe_library
    if api is None:
        handler._json(503, {"error": "workflow recipes are unavailable"})
    elif path == "/api/v1/recipes":
        handler._json(201, api.create(document))
    elif path.startswith("/api/v1/recipes/") and path.endswith("/run"):
        identifier = unquote(path.removeprefix("/api/v1/recipes/").removesuffix("/run"))
        handler._json(201, api.run(identifier, document))
    else:
        return False
    return True
