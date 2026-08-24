"""Dispatch typed Shell requests to the product engineering-loop facade."""

from fam_os.shell.engineering_candidate_contracts import (
    ShellEngineeringCandidateEditRequest,
    ShellEngineeringCandidateVerificationRequest,
    ShellEngineeringCandidateReverificationRequest,
    ShellEngineeringChangesetApplyRequest,
    ShellEngineeringChangesetPreviewRequest,
    ShellEngineeringIncidentAdvanceRequest,
    ShellEngineeringPublicationRequest,
    decode_candidate_edit_content,
)
from fam_os.shell.engineering_loop_contracts import (
    ShellEngineeringLoopMutation,
    ShellEngineeringLoopOperation,
    ShellEngineeringLoopQuery,
    ShellEngineeringLoopResponse,
    ShellEngineeringLoopStartRequest,
    ShellEngineeringLoopView,
)


class EngineeringLoopUnavailable(RuntimeError):
    """The installed product has no master engineering-loop facade."""


def dispatch_engineering_loop(api, command):
    if api is None:
        raise EngineeringLoopUnavailable
    if isinstance(command, ShellEngineeringLoopStartRequest):
        state = api.start(
            command.owner_id, command.definition, command.budget,
        )
        view = api.inspect(command.owner_id, state.task_id)
        return _response(command.request_id, ShellEngineeringLoopOperation.START, view)
    if isinstance(command, ShellEngineeringLoopQuery):
        if command.operation is ShellEngineeringLoopOperation.LIST:
            return ShellEngineeringLoopResponse(
                command.request_id, command.operation,
                views=tuple(_view(item) for item in api.tasks(command.owner_id)),
            )
        if command.operation is ShellEngineeringLoopOperation.EDITS:
            return ShellEngineeringLoopResponse(
                command.request_id, command.operation,
                edits=tuple(api.candidate_edits(command.owner_id, command.task_id)),
            )
        if command.operation is ShellEngineeringLoopOperation.VERIFICATIONS:
            return ShellEngineeringLoopResponse(
                command.request_id, command.operation,
                verifications=tuple(api.candidate_verifications(
                    command.owner_id, command.task_id,
                )),
            )
        if command.operation is ShellEngineeringLoopOperation.CHANGESETS:
            return ShellEngineeringLoopResponse(
                command.request_id, command.operation,
                changesets=tuple(api.candidate_changesets(
                    command.owner_id, command.task_id,
                )),
            )
        if command.operation is ShellEngineeringLoopOperation.INCIDENTS:
            return ShellEngineeringLoopResponse(
                command.request_id, command.operation,
                incidents=tuple(api.incidents_for_task(
                    command.owner_id, command.task_id,
                )),
                incident_evidence=tuple(api.incident_evidence_for_task(
                    command.owner_id, command.task_id,
                )),
            )
        if command.operation is ShellEngineeringLoopOperation.REVIEWS:
            return ShellEngineeringLoopResponse(
                command.request_id, command.operation,
                reviews=tuple(api.reviews_for_task(
                    command.owner_id, command.task_id,
                )),
                review_evidence=tuple(api.review_evidence_for_task(
                    command.owner_id, command.task_id,
                )),
            )
        if command.operation is ShellEngineeringLoopOperation.DOCUMENTATION:
            return ShellEngineeringLoopResponse(
                command.request_id, command.operation,
                documentation=tuple(api.documentation_for_task(
                    command.owner_id, command.task_id,
                )),
            )
        if command.operation is ShellEngineeringLoopOperation.RUNTIME_DIAGNOSTICS:
            return ShellEngineeringLoopResponse(
                command.request_id, command.operation,
                runtime_diagnostic_requests=tuple(
                    api.runtime_diagnostic_requests(
                        command.owner_id, command.task_id,
                    )
                ),
                runtime_diagnostics=tuple(api.runtime_diagnostic_receipts(
                    command.owner_id, command.task_id,
                )),
            )
        if command.operation is ShellEngineeringLoopOperation.DATABASE:
            results = tuple(api.database_results(
                command.owner_id, command.task_id,
            ))
            return ShellEngineeringLoopResponse(
                command.request_id, command.operation,
                database_plans=tuple(api.database_plans(
                    command.owner_id, command.task_id,
                )),
                database_backups=tuple(
                    item.backup for item in results if item.backup is not None
                ),
                database_verifications=tuple(
                    item.verification for item in results
                ),
                database_postapply=tuple(api.database_postapply_receipts(
                    command.owner_id, command.task_id,
                )),
            )
        return _response(
            command.request_id, command.operation,
            api.inspect(command.owner_id, command.task_id),
        )
    if isinstance(command, ShellEngineeringLoopMutation):
        value = (
            api.prepare(command.owner_id, command.task_id)
            if command.operation is ShellEngineeringLoopOperation.PREPARE
            else api.resume(command.owner_id, command.task_id)
        )
        return _response(command.request_id, command.operation, value)
    if isinstance(command, ShellEngineeringCandidateEditRequest):
        record = api.edit_candidate(
            command.owner_id, command.task_id, edit_id=command.edit_id,
            session_id=command.session_id, principal_id=command.principal_id,
            operation=command.operation, artifact=command.artifact,
            content=decode_candidate_edit_content(command),
        )
        return ShellEngineeringLoopResponse(
            command.request_id, ShellEngineeringLoopOperation.EDIT, edit=record,
        )
    if isinstance(command, ShellEngineeringCandidateReverificationRequest):
        record = api.reverify_candidate(
            command.owner_id, command.task_id,
            verification_id=command.verification_id,
            session_id=command.session_id, principal_id=command.principal_id,
            toolchain=command.toolchain, recipe_id=command.recipe_id,
            recipe_version=command.recipe_version,
        )
        return ShellEngineeringLoopResponse(
            command.request_id, ShellEngineeringLoopOperation.REVERIFY,
            verification=record,
        )
    if isinstance(command, ShellEngineeringCandidateVerificationRequest):
        record = api.verify_candidate(
            command.owner_id, command.task_id,
            verification_id=command.verification_id,
            session_id=command.session_id, principal_id=command.principal_id,
            toolchain=command.toolchain, recipe_id=command.recipe_id,
            recipe_version=command.recipe_version,
        )
        return ShellEngineeringLoopResponse(
            command.request_id, ShellEngineeringLoopOperation.VERIFY,
            verification=record,
        )
    if isinstance(command, ShellEngineeringChangesetPreviewRequest):
        record = api.preview_candidate(
            command.owner_id, command.task_id, command.changeset_id,
        )
        return ShellEngineeringLoopResponse(
            command.request_id, ShellEngineeringLoopOperation.PREVIEW,
            changeset=record,
        )
    if isinstance(command, ShellEngineeringChangesetApplyRequest):
        record = api.apply_candidate(
            command.owner_id, command.task_id, command.changeset_id,
            command.decision, session_id=command.session_id,
            principal_id=command.principal_id,
        )
        return ShellEngineeringLoopResponse(
            command.request_id, ShellEngineeringLoopOperation.APPLY,
            changeset=record,
        )
    if isinstance(command, ShellEngineeringPublicationRequest):
        receipt = api.publish_candidate(command.owner_id, command.approval)
        return ShellEngineeringLoopResponse(
            command.request_id, ShellEngineeringLoopOperation.PUBLISH,
            publication=receipt,
        )
    if isinstance(command, ShellEngineeringIncidentAdvanceRequest):
        incident = api.inspect_incident(command.owner_id, command.incident_id)
        if incident.task_id != command.task_id:
            raise PermissionError("engineering incident belongs to another task")
        incident = api.advance_incident(
            command.owner_id, command.incident_id, command.stage,
            command.evidence_id,
        )
        return ShellEngineeringLoopResponse(
            command.request_id, ShellEngineeringLoopOperation.INCIDENT_ADVANCE,
            incident=incident,
        )
    raise ValueError("unsupported Shell engineering loop request")


def _response(request_id, operation, value):
    return ShellEngineeringLoopResponse(request_id, operation, view=_view(value))


def _view(value):
    return ShellEngineeringLoopView(
        value["task_id"], value["intent"], tuple(value["workspace_roots"]),
        value["acceptance_policy_id"], value["stage"], value["revision"],
        value["task_graph_evidence_id"], value["candidate_id"],
        value["diff_checkpoint_id"], tuple(value["test_receipt_ids"]),
        tuple(value["runtime_diagnostic_receipt_ids"]),
        tuple(value["database_receipt_ids"]),
        tuple(value["database_postapply_receipt_ids"]),
        tuple(value["integration_environment_receipt_ids"]),
        tuple(value["integration_environment_postapply_receipt_ids"]),
        tuple(value["dependency_receipt_ids"]),
        tuple(value["design_preview_receipt_ids"]),
        tuple(value["rollback_receipt_ids"]), tuple(value["git_receipt_ids"]),
        value["publication_approval_id"], dict(value["budget"]),
    )
