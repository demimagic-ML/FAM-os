"""Authenticated metadata-only integration start-intent audit routes."""

from urllib.parse import unquote

from fam_os.schemas import encode_document


_PREFIX = "/api/v1/engineering/environment-start-intents"


def handle_integration_start_intent_get(handler, path):
    if path != _PREFIX and not path.startswith(_PREFIX + "/"):
        return False
    if handler._session() is None:
        handler.send_error(401); return True
    api = handler.server.integration_environment_api
    if api is None:
        handler._json(503, {"error": "Integration environments are unavailable."})
        return True
    try:
        identity = _identity(path)
        if identity is None:
            document = {
                "start_intents": [
                    _document(item) for item in api.intents(api.owner_id)
                ],
            }
        else:
            document = _document(api.inspect_intent(api.owner_id, identity))
    except KeyError:
        handler.send_error(404); return True
    except (PermissionError, TypeError, ValueError) as error:
        handler._json(403 if isinstance(error, PermissionError) else 400, {
            "error": str(error),
        }); return True
    handler._json(200, document)
    return True


def _identity(path):
    if path == _PREFIX: return None
    parts = path.removeprefix(_PREFIX + "/").split("/")
    if len(parts) != 1:
        raise ValueError("integration start-intent path is invalid")
    identity = unquote(parts[0])
    if not identity.strip() or "/" in identity:
        raise ValueError("integration start-intent identity is invalid")
    return identity


def _document(intent):
    return {
        "state": intent.state,
        "plan": encode_document(intent.plan),
        "candidate": encode_document(intent.candidate),
        "permit": None if intent.permit is None else encode_document(intent.permit),
        "recovery_receipt": (
            None
            if intent.recovery_receipt is None
            else encode_document(intent.recovery_receipt)
        ),
    }
