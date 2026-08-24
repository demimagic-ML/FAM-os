"""Verifier, repair, escalation, and strong fallback plan transitions."""

import logging
from datetime import UTC, datetime

from fam_os.core.contracts import StepOutcome
from fam_os.core.lifecycle import (
    AcceptanceEvidenceRecord,
    PlanEvidenceKind,
    PlanEvidenceReference,
    PlanLifecycleService,
)
from fam_os.core.lifecycle.attempt_contracts import AttemptKind
from fam_os.core.lifecycle.global_budget import (
    AttemptBudgetReservation,
)
from fam_os.core.production.contracts import AssuranceLevel, InferenceExecutionState
from fam_os.core.production.attempt_budget import production_attempt_budget
from fam_os.core.production.execution_state import (
    internal_capability,
    replace_execution,
    terminal_execution,
)
from fam_os.fabric import RemoteEvidenceDisposition, RemoteVerificationOutcome


LOGGER = logging.getLogger(__name__)


class VerificationFlow:
    def __init__(
        self, repositories, selector, capacity, resident_models,
        budget_ledger_factory, verifier, failure_observer=None,
    ) -> None:
        self._repositories = repositories
        self._selector = selector
        self._capacity = capacity
        self._resident_models = resident_models
        self._budget_factory = budget_ledger_factory
        self._verifier = verifier
        self._failure_observer = failure_observer

    def accept_or_withhold(self, snapshot, record):
        lifecycle = PlanLifecycleService(self._repositories.plans)
        if snapshot.plan.verification_required:
            advanced = lifecycle.advance(
                snapshot.instance_id, snapshot.revision, StepOutcome.SUCCEEDED,
            )
            if advanced.rejection is not None:
                raise RuntimeError("candidate could not enter verification")
            return self._verify(advanced.snapshot, record)
        self._finalize_unverified_remote(record)
        references = [PlanEvidenceReference(
            record.candidate_id, PlanEvidenceKind.RELEASE_CANDIDATE, None,
        )]
        remote_reference = self._remote_reference(record)
        if remote_reference is not None:
            references.append(remote_reference)
        recovery_reference = self._recovery_reference(record)
        if recovery_reference is not None:
            references.append(recovery_reference)
        advanced = lifecycle.advance(
            snapshot.instance_id, snapshot.revision, StepOutcome.SUCCEEDED,
            tuple(references),
        )
        if advanced.rejection is not None:
            raise RuntimeError("candidate could not be released")
        return advanced.snapshot, terminal_execution(self._repositories, record)

    def fallback_after_provider_failure(self, snapshot, record):
        _, prepared = self._fallback(
            PlanLifecycleService(self._repositories.plans), snapshot, record,
            "The first strong provider failed before producing a candidate.",
        )
        return prepared

    def _verify(self, snapshot, record):
        request = self._repositories.requests.get(record.request_id)
        candidate = self._repositories.final_evidence.candidate(record.candidate_id)
        if request is None or candidate is None:
            raise RuntimeError("verification inputs are missing")
        decision = self._verifier.verify(
            record.intent, request, candidate.candidate_id, candidate.content,
        )
        lifecycle = PlanLifecycleService(self._repositories.plans)
        current = next(
            item for item in snapshot.plan.steps
            if item.step_id == snapshot.current_step_id
        )
        if decision.run_record is not None and (
            decision.run_record.request_id != request.request_id
            or decision.run_record.candidate_id != candidate.candidate_id
        ):
            raise RuntimeError("verification evidence does not bind the active candidate")
        if decision.available and decision.acceptance_id not in current.acceptance_ids:
            self._finalize_remote(
                record, RemoteEvidenceDisposition.WITHHELD,
                RemoteVerificationOutcome.UNAVAILABLE,
                acceptance_id=decision.acceptance_id,
                verification_run_id=_run_id(decision),
            )
            advanced = lifecycle.advance(
                snapshot.instance_id, snapshot.revision, StepOutcome.UNAVAILABLE,
                self._remote_references(record),
            )
            return advanced.snapshot, terminal_execution(
                self._repositories, record,
                failure_code="verification.acceptance_undeclared",
                feedback="Activated verifier acceptance was not declared by the plan.",
            )
        if not decision.available:
            self._finalize_remote(
                record, RemoteEvidenceDisposition.WITHHELD,
                RemoteVerificationOutcome.UNAVAILABLE,
                acceptance_id=decision.acceptance_id,
                verification_run_id=_run_id(decision),
            )
            advanced = lifecycle.advance(
                snapshot.instance_id, snapshot.revision, StepOutcome.UNAVAILABLE,
                self._remote_references(record),
            )
            return advanced.snapshot, terminal_execution(
                self._repositories, record,
                failure_code="verification.verifier_unavailable",
                feedback=decision.feedback,
            )
        if decision.passed:
            return self._release_verified(lifecycle, snapshot, record, decision)
        self._observe_failure(record, decision)
        self._finalize_remote(
            record, RemoteEvidenceDisposition.REJECTED,
            RemoteVerificationOutcome.FAILED,
            acceptance_id=decision.acceptance_id,
            verification_run_id=_run_id(decision),
        )
        if snapshot.current_step_id == "verify-primary":
            return self._repair(lifecycle, snapshot, record, decision.feedback)
        if snapshot.current_step_id == "verify-repair":
            return self._escalate(lifecycle, snapshot, record, decision.feedback)
        if snapshot.current_step_id == "verify-escalation":
            return self._fallback(lifecycle, snapshot, record, decision.feedback)
        advanced = lifecycle.advance(
            snapshot.instance_id, snapshot.revision, StepOutcome.FAILED,
        )
        return advanced.snapshot, terminal_execution(
            self._repositories, record,
            failure_code="verification.acceptance.failed", feedback=decision.feedback,
        )

    def _observe_failure(self, record, decision) -> None:
        if self._failure_observer is None:
            return
        try:
            self._failure_observer.verification_failed(record, decision)
        except Exception:
            LOGGER.exception(
                "factory failure discovery rejected verification %s",
                _run_id(decision) or "unrecorded",
            )

    def _release_verified(self, lifecycle, snapshot, record, decision):
        evidence_id = (
            decision.run_record.verification_id
            if decision.run_record is not None
            else f"verification-{record.request_id}-{record.revision}"
        )
        acceptance = AcceptanceEvidenceRecord(
            evidence_id, record.candidate_id, (decision.acceptance_id,), True,
        )
        remote = self._remote_candidate(record)
        added = (
            self._repositories.final_evidence.add_acceptance_and_finalize_remote(
                acceptance, record.request_id, decision.acceptance_id,
                _run_id(decision), datetime.now(UTC),
            )
            if remote is not None else
            self._repositories.final_evidence.add_acceptance(acceptance)
        )
        if not added:
            raise RuntimeError("acceptance evidence already exists")
        references = (
            PlanEvidenceReference(
                record.candidate_id, PlanEvidenceKind.RELEASE_CANDIDATE, None,
            ),
            PlanEvidenceReference(
                evidence_id, PlanEvidenceKind.VERIFICATION_PASS, None,
            ),
        )
        remote_reference = self._remote_reference(record)
        if remote_reference is not None:
            references = (*references, remote_reference)
        recovery_reference = self._recovery_reference(record)
        if recovery_reference is not None:
            references = (*references, recovery_reference)
        advanced = lifecycle.advance(
            snapshot.instance_id, snapshot.revision, StepOutcome.SUCCEEDED, references,
        )
        if advanced.rejection is not None:
            raise RuntimeError("verified candidate could not be released")
        terminal = terminal_execution(
            self._repositories, record, assurance=AssuranceLevel.VERIFIED,
            feedback=decision.feedback,
        )
        return advanced.snapshot, terminal

    def _finalize_unverified_remote(self, record) -> None:
        self._finalize_remote(
            record, RemoteEvidenceDisposition.RELEASED,
            RemoteVerificationOutcome.NOT_REQUIRED,
            acceptance_id=None, verification_run_id=None,
        )

    def _finalize_remote(
        self, record, disposition, verification_outcome, *,
        acceptance_id, verification_run_id,
    ) -> None:
        if self._remote_candidate(record) is None:
            return
        self._repositories.final_evidence.finalize_remote(
            record.request_id, record.candidate_id, disposition,
            verification_outcome, acceptance_id=acceptance_id,
            acceptance_evidence_id=None,
            verification_run_id=verification_run_id,
            finalized_at=datetime.now(UTC),
        )

    def _remote_candidate(self, record):
        evidence = self._repositories.final_evidence.remote_execution_for_request(
            record.request_id,
        )
        return (
            evidence
            if evidence is not None and evidence.candidate_id == record.candidate_id
            else None
        )

    def _remote_reference(self, record):
        evidence = self._remote_candidate(record)
        return (
            None
            if evidence is None else
            PlanEvidenceReference(
                evidence.evidence_id, PlanEvidenceKind.REMOTE_EXECUTION, None,
            )
        )

    def _remote_references(self, record) -> tuple[PlanEvidenceReference, ...]:
        references = (
            self._remote_reference(record),
            self._recovery_reference(record),
        )
        return tuple(reference for reference in references if reference is not None)

    def _recovery_reference(self, record):
        evidence = self._repositories.final_evidence.remote_recovery_for_request(
            record.request_id,
        )
        return (
            None
            if evidence is None or evidence.local_candidate_id != record.candidate_id
            else PlanEvidenceReference(
                evidence.evidence_id, PlanEvidenceKind.REMOTE_RECOVERY, None,
            )
        )

    def _repair(self, lifecycle, snapshot, record, feedback):
        reservation = AttemptBudgetReservation(
            f"budget-{record.request_id}-repair", record.instance_id,
            f"attempt-{record.request_id}-repair", AttemptKind.REPAIR, 1024, 60_000,
        )
        if self._budget(record.instance_id).reserve(reservation) is None:
            return self._budget_withheld(lifecycle, snapshot, record, feedback)
        references = [PlanEvidenceReference(
            f"repair-{record.candidate_id}", PlanEvidenceKind.REPAIR_ATTEMPT,
            internal_capability(record.intent),
        )]
        remote_reference = self._remote_reference(record)
        if remote_reference is not None:
            references.append(remote_reference)
        recovery_reference = self._recovery_reference(record)
        if recovery_reference is not None:
            references.append(recovery_reference)
        advanced = lifecycle.advance(
            snapshot.instance_id, snapshot.revision, StepOutcome.FAILED,
            tuple(references),
        )
        if advanced.rejection is not None:
            raise RuntimeError("failed candidate could not enter repair")
        selection = record.selection
        if record.remote_plan is not None and record.remote_attempt_consumed:
            selection = self._selector.select(
                record.request_id, record.intent, self._capacity(),
                resident_model_refs=self._resident_models(),
                required_verifier_id=self._required_verifier_id(record.request_id),
            )
        prepared = replace_execution(
            self._repositories, record, selection=selection,
            state=InferenceExecutionState.PREPARED,
            candidate_id=None, verifier_feedback=feedback,
        )
        return advanced.snapshot, prepared

    def _escalate(self, lifecycle, snapshot, record, feedback):
        reservation = AttemptBudgetReservation(
            f"budget-{record.request_id}-escalation", record.instance_id,
            f"attempt-{record.request_id}-escalation", AttemptKind.ESCALATION,
            1024, 180_000,
        )
        if self._budget(record.instance_id).reserve(reservation) is None:
            return self._budget_withheld(lifecycle, snapshot, record, feedback)
        selection = self._selector.select(
            record.request_id, record.intent, self._capacity(), escalation=True,
            resident_model_refs=self._resident_models(),
            required_verifier_id=self._required_verifier_id(record.request_id),
        )
        return self._advance_attempt(
            lifecycle, snapshot, record, feedback, selection,
            f"failed-{record.candidate_id}",
        )

    def _fallback(self, lifecycle, snapshot, record, feedback):
        try:
            selection = self._selector.select(
                record.request_id, record.intent, self._capacity(), escalation=True,
                resident_model_refs=self._resident_models(),
                excluded_model_refs=(record.selection.model_ref,),
                required_verifier_id=self._required_verifier_id(record.request_id),
            )
        except LookupError:
            advanced = lifecycle.advance(
                snapshot.instance_id, snapshot.revision, StepOutcome.UNAVAILABLE,
            )
            terminal = terminal_execution(
                self._repositories, record,
                failure_code="expert.strong_fallback_unavailable", feedback=feedback,
            )
            return advanced.snapshot, terminal
        reservation = AttemptBudgetReservation(
            f"budget-{record.request_id}-fallback", record.instance_id,
            f"attempt-{record.request_id}-fallback", AttemptKind.ESCALATION,
            1024, 180_000,
        )
        if self._budget(record.instance_id).reserve(reservation) is None:
            return self._budget_withheld(lifecycle, snapshot, record, feedback)
        return self._advance_attempt(
            lifecycle, snapshot, record, feedback, selection,
            f"fallback-{record.candidate_id}",
        )

    def _advance_attempt(
        self, lifecycle, snapshot, record, feedback, selection, reference_id,
    ):
        reference = PlanEvidenceReference(
            reference_id, PlanEvidenceKind.ESCALATION_ATTEMPT,
            internal_capability(record.intent),
        )
        advanced = lifecycle.advance(
            snapshot.instance_id, snapshot.revision, StepOutcome.FAILED, (reference,),
        )
        if advanced.rejection is not None:
            raise RuntimeError("candidate could not enter strong attempt")
        prepared = replace_execution(
            self._repositories, record, selection=selection,
            state=InferenceExecutionState.PREPARED, candidate_id=None,
            verifier_feedback=feedback,
        )
        return advanced.snapshot, prepared

    def _budget_withheld(self, lifecycle, snapshot, record, feedback):
        advanced = lifecycle.advance(
            snapshot.instance_id, snapshot.revision, StepOutcome.UNAVAILABLE,
        )
        terminal = terminal_execution(
            self._repositories, record,
            failure_code="core.attempt_budget.exhausted", feedback=feedback,
        )
        return advanced.snapshot, terminal

    def _budget(self, instance_id):
        return self._budget_factory(production_attempt_budget(instance_id))

    def _required_verifier_id(self, request_id: str) -> str:
        declaration = self._repositories.verifications.declaration_for_request(
            request_id,
        )
        if declaration is None:
            raise RuntimeError("verified request declaration is unavailable")
        return declaration.contract.verifier_id


def _run_id(decision) -> str | None:
    return (
        None
        if decision.run_record is None
        else decision.run_record.verification_id
    )
