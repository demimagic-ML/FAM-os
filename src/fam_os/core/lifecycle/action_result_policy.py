"""Trusted pre/postcondition and recovery policy for application actions."""

from fam_os.applications import (
    ActionProposal, ActionResult, ActionStatus, ApplicationFailure,
    ApplicationFailureCategory, ApplicationRetryDisposition, ConditionEvidence,
    Reversibility,
)
from fam_os.core.lifecycle.action_execution_contracts import ActionRecoveryMetadata


def evaluate_conditions(verifier, requirements, proposal, provider_result=None):
    return tuple(
        _condition(verifier, requirement, proposal, provider_result)
        for requirement in requirements
    )


def precondition_result(proposal, evidence, completed_at):
    failed = tuple(item.condition_id for item in evidence if not item.passed)
    return ActionResult(
        proposal.proposal_id, ActionStatus.PRECONDITION_FAILED, completed_at,
        error=_failure(
            ApplicationFailureCategory.PRECONDITION_FAILED,
            "application.precondition_failed", "Action preconditions did not pass.",
            ApplicationRetryDisposition.AFTER_STATE_CHANGE, failed,
        ),
    )


def provider_failure_result(proposal, completed_at, code="application.execution_failed"):
    return ActionResult(
        proposal.proposal_id, ActionStatus.EXECUTION_FAILED, completed_at,
        error=_failure(
            ApplicationFailureCategory.EXECUTION_FAILED, code,
            "The application action could not be verified as executed.",
            ApplicationRetryDisposition.AFTER_STATE_CHANGE,
        ),
    )


def audit_failure_result(proposal, source, completed_at):
    return ActionResult(
        proposal.proposal_id, ActionStatus.EXECUTION_FAILED, completed_at,
        before_revision=source.before_revision, after_revision=source.after_revision,
        reversal_token=source.reversal_token,
        error=_failure(
            ApplicationFailureCategory.EXECUTION_FAILED,
            "application.audit_unavailable",
            "The action occurred but its required terminal audit could not be recorded.",
            ApplicationRetryDisposition.NEVER,
        ),
    )


def finalize_provider_result(proposal, provider_result, verifier, completed_at):
    if not _valid_provider_result(proposal, provider_result):
        return provider_failure_result(
            proposal, completed_at, "application.provider_result_invalid"
        )
    if provider_result.status not in (
        ActionStatus.VERIFIED, ActionStatus.POSTCONDITION_FAILED,
    ):
        return _sanitized_failure(provider_result, completed_at)
    evidence = evaluate_conditions(
        verifier, proposal.postconditions, proposal, provider_result,
    )
    if provider_result.verified and all(item.passed for item in evidence):
        if not _recovery_token_valid(proposal, provider_result):
            return provider_failure_result(
                proposal, completed_at, "application.recovery_metadata_missing"
            )
        return ActionResult(
            proposal.proposal_id, ActionStatus.VERIFIED, completed_at, evidence,
            provider_result.output, provider_result.before_revision,
            provider_result.after_revision, provider_result.reversal_token,
        )
    if any(not item.passed for item in evidence):
        return ActionResult(
            proposal.proposal_id, ActionStatus.POSTCONDITION_FAILED, completed_at,
            evidence, before_revision=provider_result.before_revision,
            after_revision=provider_result.after_revision,
            reversal_token=provider_result.reversal_token,
            error=_failure(
                ApplicationFailureCategory.POSTCONDITION_FAILED,
                "application.postcondition_failed", "Action postconditions did not pass.",
                ApplicationRetryDisposition.AFTER_STATE_CHANGE,
                tuple(item.condition_id for item in evidence if not item.passed),
            ),
        )
    return provider_failure_result(
        proposal, completed_at, "application.provider_did_not_verify"
    )


def recovery_metadata(proposal: ActionProposal, result: ActionResult, provider_invoked: bool):
    recoverable = proposal.reversibility in (
        Reversibility.REVERSIBLE, Reversibility.COMPENSATABLE,
    )
    return ActionRecoveryMetadata(
        proposal.reversibility,
        proposal.reversal_capability_id if recoverable else None,
        result.reversal_token if recoverable else None,
        provider_invoked and not result.verified and recoverable,
    )


def _condition(verifier, requirement, proposal, provider_result):
    try:
        evidence = verifier.verify(requirement, proposal, provider_result)
    except Exception:
        evidence = None
    if (
        isinstance(evidence, ConditionEvidence)
        and evidence.condition_id == requirement.condition_id
        and evidence.verifier_id == requirement.verifier_id
    ):
        return evidence
    return ConditionEvidence(
        requirement.condition_id, requirement.verifier_id, False,
        "Required condition verifier was unavailable.",
    )


def _valid_provider_result(proposal, result):
    if not isinstance(result, ActionResult) or result.proposal_id != proposal.proposal_id:
        return False
    expected = proposal.request.expected_revision
    if expected is not None and result.before_revision != expected:
        return False
    if proposal.reversibility is Reversibility.IRREVERSIBLE and result.reversal_token is not None:
        return False
    return True


def _recovery_token_valid(proposal, result):
    recoverable = proposal.reversibility in (
        Reversibility.REVERSIBLE, Reversibility.COMPENSATABLE,
    )
    return not recoverable or result.reversal_token is not None


def _sanitized_failure(result, completed_at):
    evidence = result.postcondition_evidence if result.status is ActionStatus.POSTCONDITION_FAILED else ()
    return ActionResult(
        result.proposal_id, result.status, completed_at, evidence,
        before_revision=result.before_revision, after_revision=result.after_revision,
        reversal_token=result.reversal_token, error=result.error,
    )


def _failure(category, code, message, retry, evidence=()):
    return ApplicationFailure(category, code, message, retry, tuple(evidence))
