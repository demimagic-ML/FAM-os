"""Authenticated Console routes for the persistent engineering lifecycle."""

import base64
from urllib.parse import unquote

from fam_os.core.engineering import (
    CandidateArtifact, CandidateOperation, EngineeringLoopBudget,
    CheckpointDecision, EngineeringTaskDefinition, GitPublicationApproval,
    EngineeringIncidentStage,
)
from fam_os.schemas import decode_document, encode_document


_PREFIX = "/api/v1/engineering/tasks"
_BUDGET_FIELDS = {
    "maximum_tokens", "maximum_wall_seconds", "maximum_commands",
    "maximum_network_bytes", "maximum_files", "maximum_storage_bytes",
}
_EDIT_FIELDS = {
    "owner_id", "edit_id", "session_id", "principal_id", "operation",
    "artifact", "content_base64", "confirmed",
}
_VERIFY_FIELDS = {
    "owner_id", "verification_id", "session_id", "principal_id",
    "toolchain", "recipe_id", "recipe_version", "confirmed",
}
_PREVIEW_FIELDS = {"owner_id", "changeset_id", "confirmed"}
_APPLY_FIELDS = {
    "owner_id", "changeset_id", "decision", "session_id", "principal_id",
    "confirmed",
}
_MAX_EDIT_CONTENT_BYTES = 131_072


def handle_engineering_loop_get(handler, path: str) -> bool:
    if not _matches(path):
        return False
    if handler._session() is None:
        handler.send_error(401)
        return True
    api = handler.server.engineering_loop_api
    if api is None:
        handler._json(503, {"error": "Engineering lifecycle is unavailable."})
        return True
    try:
        task_id, operation = _path(path)
        if operation == "list":
            response = {"tasks": list(api.tasks(api.owner_id))}
        elif operation == "edits":
            response = {
                "edits": [encode_document(item) for item in api.candidate_edits(api.owner_id, task_id)],
            }
        elif operation == "verifications":
            response = {
                "verifications": [
                    encode_document(item)
                    for item in api.candidate_verifications(api.owner_id, task_id)
                ],
            }
        elif operation == "changesets":
            response = {
                "changesets": [
                    encode_document(item)
                    for item in api.candidate_changesets(api.owner_id, task_id)
                ],
            }
        elif operation == "incidents":
            response = {
                "incidents": [
                    encode_document(item)
                    for item in api.incidents_for_task(api.owner_id, task_id)
                ],
                "evidence": [
                    encode_document(item)
                    for item in api.incident_evidence_for_task(
                        api.owner_id, task_id,
                    )
                ],
            }
        elif operation == "reviews":
            response = {
                "reviews": [
                    encode_document(item)
                    for item in api.reviews_for_task(api.owner_id, task_id)
                ],
                "evidence": [
                    encode_document(item)
                    for item in api.review_evidence_for_task(
                        api.owner_id, task_id,
                    )
                ],
            }
        elif operation == "documentation":
            response = {
                "documentation": [
                    encode_document(item)
                    for item in api.documentation_for_task(api.owner_id, task_id)
                ],
            }
        elif operation == "runtime-diagnostics":
            response = {
                "requests": [
                    encode_document(item)
                    for item in api.runtime_diagnostic_requests(
                        api.owner_id, task_id,
                    )
                ],
                "receipts": [
                    encode_document(item)
                    for item in api.runtime_diagnostic_receipts(
                        api.owner_id, task_id,
                    )
                ],
            }
        elif operation == "database":
            results = api.database_results(api.owner_id, task_id)
            response = {
                "plans": [
                    encode_document(item)
                    for item in api.database_plans(api.owner_id, task_id)
                ],
                "backups": [
                    encode_document(item.backup) for item in results
                    if item.backup is not None
                ],
                "verifications": [
                    encode_document(item.verification) for item in results
                ],
                "postapply": [
                    encode_document(item)
                    for item in api.database_postapply_receipts(
                        api.owner_id, task_id,
                    )
                ],
            }
        else:
            response = api.inspect(api.owner_id, task_id)
    except KeyError:
        handler.send_error(404)
        return True
    except PermissionError as error:
        handler._json(403, {"error": str(error)})
        return True
    except (TypeError, ValueError) as error:
        handler._json(400, {"error": str(error)})
        return True
    handler._json(200, response)
    return True


def handle_engineering_loop_post(handler, path: str, document: dict) -> bool:
    if not _matches(path):
        return False
    api = handler.server.engineering_loop_api
    if api is None:
        handler._json(503, {"error": "Engineering lifecycle is unavailable."})
        return True
    task_id, operation = _path(path)
    if operation == "start":
        _exact(document, {"owner_id", "definition", "budget", "confirmed"})
        _confirmed(document)
        budget = document["budget"]
        if not isinstance(budget, dict) or set(budget) != _BUDGET_FIELDS:
            raise ValueError("engineering lifecycle budget fields must match exactly")
        definition = decode_document(document["definition"])
        if not isinstance(definition, EngineeringTaskDefinition):
            raise ValueError("engineering task definition schema is invalid")
        response = api.start(
            _text(document["owner_id"]), definition,
            EngineeringLoopBudget(**budget),
        )
        response = api.inspect(api.owner_id, response.task_id)
    elif operation in {"resume", "prepare"} and task_id is not None:
        _exact(document, {"owner_id", "confirmed"})
        _confirmed(document)
        method = api.prepare if operation == "prepare" else api.resume
        response = method(_text(document["owner_id"]), task_id)
    elif operation == "edit" and task_id is not None:
        _exact(document, _EDIT_FIELDS)
        _confirmed(document)
        operation_value = decode_document(document["operation"])
        if not isinstance(operation_value, CandidateOperation):
            raise ValueError("candidate edit operation schema is invalid")
        artifact_value = None
        if document["artifact"] is not None:
            artifact_value = decode_document(document["artifact"])
            if not isinstance(artifact_value, CandidateArtifact):
                raise ValueError("candidate edit artifact schema is invalid")
        content = _content(document["content_base64"], artifact_value is not None)
        record = api.edit_candidate(
            _text(document["owner_id"]), task_id,
            edit_id=_text(document["edit_id"]),
            session_id=_text(document["session_id"]),
            principal_id=_text(document["principal_id"]),
            operation=operation_value, artifact=artifact_value, content=content,
        )
        response = {"edit": encode_document(record)}
    elif operation in {"verify", "reverify"} and task_id is not None:
        _exact(document, _VERIFY_FIELDS)
        _confirmed(document)
        method = (
            api.reverify_candidate if operation == "reverify"
            else api.verify_candidate
        )
        record = method(
            _text(document["owner_id"]), task_id,
            verification_id=_text(document["verification_id"]),
            session_id=_text(document["session_id"]),
            principal_id=_text(document["principal_id"]),
            toolchain=_text(document["toolchain"]),
            recipe_id=_text(document["recipe_id"]),
            recipe_version=_text(document["recipe_version"]),
        )
        response = {"verification": encode_document(record)}
    elif operation == "preview" and task_id is not None:
        _exact(document, _PREVIEW_FIELDS)
        _confirmed(document)
        record = api.preview_candidate(
            _text(document["owner_id"]), task_id,
            _text(document["changeset_id"]),
        )
        response = {"changeset": encode_document(record)}
    elif operation == "apply" and task_id is not None:
        _exact(document, _APPLY_FIELDS)
        _confirmed(document)
        decision = decode_document(document["decision"])
        if not isinstance(decision, CheckpointDecision):
            raise ValueError("candidate checkpoint decision schema is invalid")
        record = api.apply_candidate(
            _text(document["owner_id"]), task_id,
            _text(document["changeset_id"]), decision,
            session_id=_text(document["session_id"]),
            principal_id=_text(document["principal_id"]),
        )
        response = {"changeset": encode_document(record)}
    elif operation == "publish" and task_id is not None:
        _exact(document, {"owner_id", "approval", "confirmed"})
        _confirmed(document)
        approval = decode_document(document["approval"])
        if (
            not isinstance(approval, GitPublicationApproval)
            or approval.task_id != task_id
        ):
            raise ValueError("Git publication approval schema or task is invalid")
        receipt = api.publish_candidate(
            _text(document["owner_id"]), approval,
        )
        response = {"publication": encode_document(receipt)}
    elif operation == "incident-advance" and task_id is not None:
        _exact(document, {
            "owner_id", "incident_id", "stage", "evidence_id", "confirmed",
        })
        _confirmed(document)
        stage = EngineeringIncidentStage(_text(document["stage"]))
        incident = api.inspect_incident(
            _text(document["owner_id"]), _text(document["incident_id"]),
        )
        if incident.task_id != task_id:
            raise PermissionError("engineering incident belongs to another task")
        response = {"incident": encode_document(api.advance_incident(
            _text(document["owner_id"]), incident.incident_id, stage,
            _text(document["evidence_id"]),
        ))}
    else:
        raise ValueError("engineering lifecycle mutation path is invalid")
    handler._json(200, response)
    return True


def _path(path: str) -> tuple[str | None, str]:
    parts = path.strip("/").split("/")
    if parts[:4] != ["api", "v1", "engineering", "tasks"]:
        raise ValueError("engineering lifecycle path is invalid")
    if len(parts) == 4:
        return None, "list"
    if len(parts) == 5 and parts[4] == "start":
        return None, "start"
    if len(parts) not in {5, 6}:
        raise ValueError("engineering lifecycle path is invalid")
    task_id = unquote(parts[4])
    if not task_id.strip() or "/" in task_id:
        raise ValueError("engineering task identifier is invalid")
    operation = "inspect" if len(parts) == 5 else parts[5]
    if operation not in {
        "inspect", "resume", "prepare", "edit", "edits", "verify",
        "verifications",
        "preview", "apply", "changesets", "reverify", "publish",
        "incidents", "incident-advance", "reviews", "documentation",
        "runtime-diagnostics",
        "database",
    }:
        raise ValueError("engineering lifecycle operation is invalid")
    return task_id, operation


def _matches(path: str) -> bool:
    return path == _PREFIX or path.startswith(_PREFIX + "/")


def _exact(document, fields) -> None:
    if not isinstance(document, dict) or set(document) != fields:
        raise ValueError("engineering lifecycle fields must match exactly")


def _confirmed(document) -> bool:
    if document["confirmed"] is not True:
        raise PermissionError("engineering lifecycle action requires confirmation")
    return True


def _text(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("engineering lifecycle field must be non-empty text")
    return value


def _content(value, required: bool) -> bytes | None:
    if value is None:
        if required:
            raise ValueError("candidate edit artifact content is required")
        return None
    if not isinstance(value, str) or len(value) > 174_764:
        raise ValueError("candidate edit content exceeds its transport bound")
    try:
        content = base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise ValueError("candidate edit content is not strict base64") from error
    if len(content) > _MAX_EDIT_CONTENT_BYTES or not required:
        raise ValueError("candidate edit content is invalid for its artifact")
    return content
