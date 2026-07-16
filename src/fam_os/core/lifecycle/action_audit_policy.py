"""Content-free audit projection for application action execution."""

import hashlib

from fam_os.applications import (
    ActionAuditStage, ActionStatus, ApplicationActionAuditIntent,
)


def requested_audit(command, authorized, operation_id, event_id, occurred_at):
    proposal = command.proposal
    return _intent(
        command, authorized, operation_id, event_id, occurred_at,
        ActionAuditStage.REQUESTED,
        condition_ids=_unique(
            item.condition_id for item in (*proposal.preconditions, *proposal.postconditions)
        ),
    )


def terminal_audit(
    command, authorized, operation_id, event_id, occurred_at,
    action_result, condition_ids,
):
    stage = {
        ActionStatus.VERIFIED: ActionAuditStage.VERIFIED,
        ActionStatus.PRECONDITION_FAILED: ActionAuditStage.PRECONDITION_FAILED,
        ActionStatus.POSTCONDITION_FAILED: ActionAuditStage.POSTCONDITION_FAILED,
    }.get(action_result.status, ActionAuditStage.EXECUTION_FAILED)
    failure_code = action_result.error.code if action_result.error is not None else None
    return _intent(
        command, authorized, operation_id, event_id, occurred_at, stage,
        condition_ids=condition_ids, result_status=action_result.status,
        reversal_available=action_result.reversal_token is not None,
        failure_code=failure_code,
    )


def _intent(
    command, authorized, operation_id, event_id, occurred_at, stage, *,
    condition_ids=(), result_status=None, reversal_available=False, failure_code=None,
):
    proposal = command.proposal
    permission = command.routed.admitted.permission
    resource = proposal.request.resource_uri
    resource_digest = hashlib.sha256(resource.encode()).hexdigest() if resource else None
    return ApplicationActionAuditIntent(
        event_id, operation_id, occurred_at, command.routed.request_id,
        command.plan_instance_id, permission.principal_id, permission.session_id,
        authorized.entry.application_id, authorized.entry.instance_id,
        authorized.entry.capability_id, proposal.request.permission_grant_id,
        proposal.proposal_id, command.confirmation.confirmation_id, stage,
        resource_digest, tuple(condition_ids), result_status,
        proposal.reversal_capability_id, reversal_available, failure_code,
    )


def _unique(values):
    return tuple(dict.fromkeys(values))
