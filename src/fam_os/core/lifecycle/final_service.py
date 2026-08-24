"""Safe terminal plan snapshot to TaskResult policy."""

from dataclasses import dataclass

from fam_os.core.contracts import (
    DegradationDisposition,
    FailureCategory,
    FailureComponent,
    FailureEnvelope,
    PlanStepKind,
    ResultKind,
    ResultStatus,
    ResultAssurance,
    RetryDisposition,
    TaskResult,
    TerminalDisposition,
)
from fam_os.core.lifecycle.contracts import PlanEvidenceKind
from fam_os.core.lifecycle.action_receipt_policy import verified_action_receipt
from fam_os.core.lifecycle.final_contracts import FinalResultOutcome
from fam_os.core.lifecycle.final_ports import FinalEvidenceRegistry
from fam_os.fabric import (
    RemoteEvidenceDisposition,
    RemoteVerificationOutcome,
    RemoteRecoveryDisposition,
)


@dataclass(slots=True)
class FinalResultPolicy:
    evidence: FinalEvidenceRegistry

    def assemble(self, snapshot) -> FinalResultOutcome:
        if not snapshot.terminal:
            return _rejected("final.nonterminal")
        degradations = self._degradations(snapshot)
        if degradations is None:
            return _rejected("final.missing_degradation_evidence")
        blocking = tuple(
            item for item in degradations
            if item.disposition is not DegradationDisposition.CONTINUE
        )
        if blocking:
            return FinalResultOutcome(self._blocked(snapshot, degradations, blocking[0]))
        if snapshot.terminal_disposition is TerminalDisposition.RELEASE:
            return self._release(snapshot, degradations)
        return FinalResultOutcome(self._nonrelease(snapshot, degradations))

    def _release(self, snapshot, degradations) -> FinalResultOutcome:
        event = snapshot.events[-1]
        candidates = _refs(event, PlanEvidenceKind.RELEASE_CANDIDATE)
        if len(candidates) != 1:
            return _rejected("final.candidate_reference_required")
        candidate = self.evidence.candidate(candidates[0].reference_id)
        if not _candidate_matches(candidate, snapshot):
            return _rejected("final.invalid_candidate_evidence")
        assert candidate is not None
        evidence_ids = [candidate.candidate_id]
        accepted = None
        if snapshot.plan.verification_required:
            accepted = self._accepted(snapshot, candidate.candidate_id)
            if accepted is None:
                return _rejected("final.acceptance_evidence_required")
            evidence_ids.append(accepted.evidence_id)
            status, verified = ResultStatus.VERIFIED, True
            assurance = ResultAssurance.VERIFIED
        else:
            status, verified = ResultStatus.COMPLETED, False
            observations = tuple(
                ref.reference_id for event in snapshot.events
                for ref in event.evidence_refs
                if ref.kind is PlanEvidenceKind.OBSERVATION
            )
            evidence_ids.extend(observations)
            assurance = (
                ResultAssurance.GROUNDED
                if observations else ResultAssurance.UNVERIFIED
            )
        remote = self._remote_release(snapshot, candidate.candidate_id, accepted)
        if remote is False:
            return _rejected("final.invalid_remote_execution_evidence")
        if remote is not None:
            evidence_ids.append(remote.evidence_id)
        recovery = self._recovery_release(snapshot, candidate.candidate_id)
        if recovery is False:
            return _rejected("final.invalid_remote_recovery_evidence")
        if recovery is not None:
            evidence_ids.append(recovery.evidence_id)
        receipt = None
        if _has_action(snapshot):
            receipt = verified_action_receipt(snapshot, candidate)
            if receipt is None:
                return _rejected("final.action_receipt_evidence_required")
            evidence_ids.extend(receipt.evidence_ids)
        evidence_ids.extend(_degradation_evidence(degradations))
        result_kind = _released_result_kind(snapshot, assurance)
        if result_kind is ResultKind.ACTION_RECEIPT and not verified:
            return _rejected("final.action_receipt_requires_verification")
        return FinalResultOutcome(TaskResult(
            snapshot.plan.request_id, status,
            candidate.content if receipt is None else receipt.content,
            verified=verified,
            plan_id=snapshot.plan.plan_id, evidence_ids=tuple(dict.fromkeys(evidence_ids)),
            degradations=degradations, assurance=assurance,
            result_kind=result_kind,
        ))

    def _accepted(self, snapshot, candidate_id):
        refs = _refs(snapshot.events[-1], PlanEvidenceKind.VERIFICATION_PASS)
        if len(refs) != 1:
            return None
        accepted = self.evidence.acceptance(refs[0].reference_id)
        source = _step(snapshot.plan, snapshot.events[-1].source_step_id)
        if accepted is None or not accepted.passed or accepted.candidate_id != candidate_id:
            return None
        if not set(source.acceptance_ids) <= set(accepted.acceptance_ids):
            return None
        return accepted

    def _remote_release(self, snapshot, candidate_id, acceptance):
        references = _refs(snapshot.events[-1], PlanEvidenceKind.REMOTE_EXECUTION)
        if not references:
            return None
        if len(references) != 1:
            return False
        evidence = self.evidence.remote_execution(references[0].reference_id)
        if (
            evidence is None
            or evidence.request_id != snapshot.plan.request_id
            or evidence.candidate_id != candidate_id
            or evidence.disposition is not RemoteEvidenceDisposition.RELEASED
        ):
            return False
        if snapshot.plan.verification_required:
            if (
                evidence.verification_outcome is not RemoteVerificationOutcome.PASSED
                or acceptance is None
                or evidence.acceptance_evidence_id != acceptance.evidence_id
            ):
                return False
        elif evidence.verification_outcome is not RemoteVerificationOutcome.NOT_REQUIRED:
            return False
        return evidence

    def _degradations(self, snapshot):
        references = tuple(
            ref for event in snapshot.events for ref in event.evidence_refs
            if ref.kind is PlanEvidenceKind.DEGRADATION
        )
        resolved = tuple(self.evidence.degradation(ref.reference_id) for ref in references)
        if any(item is None for item in resolved):
            return None
        return resolved

    def _recovery_release(self, snapshot, candidate_id):
        references = _refs(snapshot.events[-1], PlanEvidenceKind.REMOTE_RECOVERY)
        if not references:
            return None
        if len(references) != 1:
            return False
        evidence = self.evidence.remote_recovery(references[0].reference_id)
        if (
            evidence is None
            or evidence.request_id != snapshot.plan.request_id
            or evidence.local_candidate_id != candidate_id
            or evidence.disposition is not RemoteRecoveryDisposition.RECOVERED
            or not evidence.unchanged_acceptance
            or not evidence.local_retry_allowed
            or evidence.raw_content_retained
            or evidence.partial_output_retained
        ):
            return False
        return evidence

    def _blocked(self, snapshot, degradations, blocker):
        message = blocker.safe_message
        failure = _failure(
            snapshot, FailureCategory.PERMISSION_DENIED,
            "core.degradation.blocked", message, RetryDisposition.AFTER_USER_ACTION,
            tuple(_degradation_evidence(degradations)),
        )
        evidence_ids = tuple(dict.fromkeys(
            (*failure.evidence_ids, *_degradation_evidence(degradations))
        ))
        return TaskResult(
            snapshot.plan.request_id, ResultStatus.WITHHELD, None, reason=message,
            plan_id=snapshot.plan.plan_id, evidence_ids=evidence_ids,
            failure=failure, degradations=degradations,
            result_kind=_nonrelease_result_kind(snapshot),
        )

    def _nonrelease(self, snapshot, degradations):
        category, code, message, retry = _terminal_failure(snapshot)
        evidence_ids = tuple(dict.fromkeys(
            (*_safe_terminal_evidence(snapshot), *_degradation_evidence(degradations))
        ))
        failure = _failure(snapshot, category, code, message, retry, evidence_ids)
        status = (
            ResultStatus.FAILED
            if snapshot.terminal_disposition is TerminalDisposition.FAIL
            else ResultStatus.WITHHELD
        )
        return TaskResult(
            snapshot.plan.request_id, status, None, reason=message,
            plan_id=snapshot.plan.plan_id, evidence_ids=evidence_ids,
            failure=failure, degradations=degradations,
            result_kind=_nonrelease_result_kind(snapshot),
        )


def _terminal_failure(snapshot):
    kinds = {ref.kind for ref in snapshot.events[-1].evidence_refs}
    failed_codes = {
        ref.reference_id for ref in snapshot.events[-1].evidence_refs
        if ref.kind is PlanEvidenceKind.FAILURE_REASON
    }
    if PlanEvidenceKind.CANCELLATION in kinds:
        return FailureCategory.CANCELLED, "core.request.cancelled", "The request was cancelled.", RetryDisposition.NEVER
    if PlanEvidenceKind.TIMEOUT in kinds:
        return FailureCategory.TIMEOUT, "core.request.timed_out", "The request exceeded its deadline.", RetryDisposition.WITH_BACKOFF
    if PlanEvidenceKind.PERMISSION_EXPIRY in kinds:
        return FailureCategory.PERMISSION_DENIED, "core.permission.expired", "Permission expired before completion.", RetryDisposition.AFTER_USER_ACTION
    if "application.action.scope_unsupported" in failed_codes:
        return (
            FailureCategory.INVALID_REQUEST,
            "application.action.scope_unsupported",
            "This request needs the iterative workspace agent because it includes "
            "operations the legacy atomic patch capability cannot represent, such as "
            "creating files, deleting files, or running commands. No action was "
            "executed by this legacy route; the original request should be preserved.",
            RetryDisposition.AFTER_USER_ACTION,
        )
    if "application.action.parameters_invalid" in failed_codes:
        return (
            FailureCategory.INVALID_REQUEST,
            "application.action.parameters_invalid",
            "FAM could not produce a valid bounded file proposal after repair and "
            "available stronger-model escalation. No action was executed by this "
            "legacy route; the original request should be handled by the iterative "
            "workspace agent without narrowing its scope.",
            RetryDisposition.AFTER_USER_ACTION,
        )
    if snapshot.terminal_disposition is TerminalDisposition.FAIL:
        return FailureCategory.INTERNAL, "core.plan.failed", "The execution plan failed safely.", RetryDisposition.NEVER
    return FailureCategory.VERIFICATION_FAILED, "core.result.withheld", "The result was withheld by policy.", RetryDisposition.NEVER


def _failure(snapshot, category, code, message, retry, evidence_ids=()):
    return FailureEnvelope(
        f"{snapshot.instance_id}:final", category, code, message,
        FailureComponent.CORE, retry, evidence_ids=evidence_ids,
    )


def _safe_terminal_evidence(snapshot):
    unsafe = {
        PlanEvidenceKind.FAILURE_REASON,
        PlanEvidenceKind.FAILED_ATTEMPT,
        PlanEvidenceKind.REPAIR_ATTEMPT,
        PlanEvidenceKind.ESCALATION_ATTEMPT,
    }
    return tuple(
        ref.reference_id for ref in snapshot.events[-1].evidence_refs
        if ref.kind not in unsafe
    )


def _candidate_matches(candidate, snapshot):
    return candidate is not None and candidate.request_id == snapshot.plan.request_id and candidate.plan_id == snapshot.plan.plan_id


def _refs(event, kind):
    return tuple(ref for ref in event.evidence_refs if ref.kind is kind)


def _step(plan, step_id):
    return next(step for step in plan.steps if step.step_id == step_id)


def _degradation_evidence(degradations):
    return tuple(evidence_id for item in degradations for evidence_id in item.evidence_ids)


def _released_result_kind(snapshot, assurance):
    if _has_action(snapshot):
        return ResultKind.ACTION_RECEIPT
    if assurance is not ResultAssurance.UNVERIFIED:
        return ResultKind.GROUNDED_ANSWER
    return ResultKind.CONVERSATION_ANSWER


def _nonrelease_result_kind(snapshot):
    if _has_action(snapshot):
        return ResultKind.ACTION_PROPOSAL
    return ResultKind.CONVERSATION_ANSWER


def _has_action(snapshot):
    return any(
        step.kind is PlanStepKind.EXECUTE_ACTION for step in snapshot.plan.steps
    )


def _rejected(code):
    return FinalResultOutcome(rejection_code=code)
