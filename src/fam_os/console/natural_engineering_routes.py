"""Authenticated Console routes for natural-language engineering proposals."""

from urllib.parse import unquote

from fam_os.core.agent import AgentAuthorityProfile


_PREFIX = "/api/v1/engineering/natural-language/proposals"


def handle_natural_engineering_get(handler, path: str) -> bool:
    if not path.startswith(_PREFIX + "/"):
        return False
    if handler._session() is None:
        handler.send_error(401)
        return True
    api = handler.server.natural_engineering_api
    if api is None:
        handler._json(503, {"error": "Natural engineering is unavailable."})
        return True
    proposal_id, operation = _path(path)
    if operation not in {"inspect", "progress"}:
        raise ValueError("natural engineering read path is invalid")
    try:
        response = (
            api.progress(api.owner_id, proposal_id)
            if operation == "progress"
            else api.inspect(api.owner_id, proposal_id)
        )
    except KeyError:
        handler.send_error(404)
        return True
    handler._json(200, response)
    return True


def handle_natural_engineering_post(
    handler, path: str, document: dict, session_id: str,
) -> bool:
    if path != _PREFIX and not path.startswith(_PREFIX + "/"):
        return False
    api = handler.server.natural_engineering_api
    if api is None:
        handler._json(503, {"error": "Natural engineering is unavailable."})
        return True
    if path == _PREFIX:
        _exact(document, {"prompt", "workspace_root", "authority_profile"})
        response = api.propose(
            api.owner_id, _text(document["prompt"]),
            _text(document["workspace_root"]),
            transport_session_id=session_id,
            authority_profile=AgentAuthorityProfile(
                _text(document["authority_profile"]),
            ),
        )
    else:
        proposal_id, operation = _path(path)
        if operation not in {
            "activate", "integration-resource-decision", "changeset-decision",
            "publication-decision", "rollback",
            "review-waiver",
        }:
            raise ValueError("natural engineering mutation path is invalid")
        if operation == "activate":
            _exact(document, {"confirmed"})
            response = api.activate(
                api.owner_id, proposal_id, session_id,
                confirmed=document["confirmed"],
            )
        elif operation == "integration-resource-decision":
            _exact(document, {"confirmed"})
            response = api.approve_integration_resources(
                api.owner_id, proposal_id, session_id,
                confirmed=document["confirmed"],
            )
        elif operation == "changeset-decision":
            _exact(document, {"changeset_id", "confirmed"})
            response = api.approve_changeset(
                api.owner_id, proposal_id, _text(document["changeset_id"]),
                session_id, confirmed=document["confirmed"],
            )
        elif operation == "publication-decision":
            _exact(document, {"publication_proposal_id", "confirmed"})
            response = api.approve_publication(
                api.owner_id, proposal_id,
                _text(document["publication_proposal_id"]), session_id,
                confirmed=document["confirmed"],
            )
        elif operation == "review-waiver":
            _exact(document, {
                "checkpoint_id", "finding_id", "consequences_sha256",
                "confirmed",
            })
            response = api.waive_review(
                api.owner_id, proposal_id,
                _text(document["checkpoint_id"]),
                _text(document["finding_id"]),
                _text(document["consequences_sha256"]),
                session_id, confirmed=document["confirmed"],
            )
        else:
            _exact(document, {"rollback_id", "confirmed"})
            response = api.rollback(
                api.owner_id, proposal_id, _text(document["rollback_id"]),
                session_id, confirmed=document["confirmed"],
            )
    handler._json(200, response)
    return True


def _path(path: str) -> tuple[str, str]:
    parts = path.strip("/").split("/")
    if (
        len(parts) not in {6, 7}
        or parts[:5] != [
            "api", "v1", "engineering", "natural-language", "proposals",
        ]
    ):
        raise ValueError("natural engineering path is invalid")
    proposal_id = unquote(parts[5])
    if not proposal_id.strip() or "/" in proposal_id:
        raise ValueError("natural engineering proposal identifier is invalid")
    operation = "inspect" if len(parts) == 6 else parts[6]
    if operation not in {
        "inspect", "progress", "activate", "integration-resource-decision",
        "changeset-decision", "rollback",
        "publication-decision",
        "review-waiver",
    }:
        raise ValueError("natural engineering operation is invalid")
    return proposal_id, operation


def _exact(document, fields) -> None:
    if not isinstance(document, dict) or set(document) != fields:
        raise ValueError("natural engineering fields must match exactly")


def _text(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("natural engineering text must be non-empty")
    return value
