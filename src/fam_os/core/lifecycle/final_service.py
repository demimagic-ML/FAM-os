"""Safe terminal plan snapshot to TaskResult policy."""

from dataclasses import dataclass

from fam_os.core.contracts import (
    DegradationDisposition,
    FailureCategory,
    FailureComponent,
    FailureEnvelope,
    ResultStatus,
    RetryDisposition,
    TaskResult,
    TerminalDisposition,
)
from fam_os.core.lifecycle.contracts import PlanEvidenceKind
from fam_os.core.lifecycle.final_contracts import FinalResultOutcome
from fam_os.core.lifecycle.final_ports import FinalEvidenceRegistry


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
        evidence_ids = [candidate.candidate_id]
        if snapshot.plan.verification_required:
            accepted = self._accepted(snapshot, candidate.candidate_id)
            if accepted is None:
                return _rejected("final.acceptance_evidence_required")
            evidence_ids.append(accepted.evidence_id)
            status, verified = ResultStatus.VERIFIED, True
        else:
            status, verified = ResultStatus.COMPLETED, False
        evidence_ids.extend(_degradation_evidence(degradations))
        return FinalResultOutcome(TaskResult(
            snapshot.plan.request_id, status, candidate.content, verified=verified,
            plan_id=snapshot.plan.plan_id, evidence_ids=tuple(dict.fromkeys(evidence_ids)),
            degradations=degradations,
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

    def _degradations(self, snapshot):
        references = tuple(
            ref for event in snapshot.events for ref in event.evidence_refs
            if ref.kind is PlanEvidenceKind.DEGRADATION
        )
        resolved = tuple(self.evidence.degradation(ref.reference_id) for ref in references)
        if any(item is None for item in resolved):
            return None
        return resolved

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
        )


def _terminal_failure(snapshot):
    kinds = {ref.kind for ref in snapshot.events[-1].evidence_refs}
    if PlanEvidenceKind.CANCELLATION in kinds:
        return FailureCategory.CANCELLED, "core.request.cancelled", "The request was cancelled.", RetryDisposition.NEVER
    if PlanEvidenceKind.TIMEOUT in kinds:
        return FailureCategory.TIMEOUT, "core.request.timed_out", "The request exceeded its deadline.", RetryDisposition.WITH_BACKOFF
    if PlanEvidenceKind.PERMISSION_EXPIRY in kinds:
        return FailureCategory.PERMISSION_DENIED, "core.permission.expired", "Permission expired before completion.", RetryDisposition.AFTER_USER_ACTION
    if snapshot.terminal_disposition is TerminalDisposition.FAIL:
        return FailureCategory.INTERNAL, "core.plan.failed", "The execution plan failed safely.", RetryDisposition.NEVER
    return FailureCategory.VERIFICATION_FAILED, "core.result.withheld", "The result was withheld by policy.", RetryDisposition.NEVER


def _failure(snapshot, category, code, message, retry, evidence_ids=()):
    return FailureEnvelope(
        f"{snapshot.instance_id}:final", category, code, message,
        FailureComponent.CORE, retry, evidence_ids=evidence_ids,
    )


def _safe_terminal_evidence(snapshot):
    unsafe = {PlanEvidenceKind.FAILED_ATTEMPT, PlanEvidenceKind.REPAIR_ATTEMPT, PlanEvidenceKind.ESCALATION_ATTEMPT}
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


def _rejected(code):
    return FinalResultOutcome(rejection_code=code)
