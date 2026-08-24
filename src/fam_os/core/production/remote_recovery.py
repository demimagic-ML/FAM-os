"""Acceptance binding and failure classification for remote loss recovery."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from fam_os.core.lifecycle import AttemptBudgetReservation
from fam_os.core.contracts import StepOutcome
from fam_os.core.lifecycle import (
    PlanEvidenceKind,
    PlanEvidenceReference,
    PlanLifecycleService,
)
from fam_os.core.lifecycle.attempt_contracts import AttemptKind
from fam_os.core.production.attempt_budget import production_attempt_budget
from fam_os.core.production.contracts import InferenceExecutionState
from fam_os.core.production.execution_state import replace_execution, terminal_execution
from fam_os.fabric import (
    RemoteAttemptFailure,
    RemoteEvidenceDisposition,
    RemoteRecoveryDisposition,
    RemoteRecoveryEvidence,
)
from fam_os.schemas import dumps_document


_RETRYABLE = frozenset({
    RemoteAttemptFailure.DISCONNECTED,
    RemoteAttemptFailure.TIMEOUT,
    RemoteAttemptFailure.PARTIAL_RESULT,
    RemoteAttemptFailure.UNCERTAIN_COMPLETION,
    RemoteAttemptFailure.REMOTE_PROVIDER_FAILED,
})


def accepted_remote_contract_sha256(
    repositories,
    record,
    snapshot,
    *,
    observed_at: datetime | None = None,
) -> str:
    request = repositories.requests.get(record.request_id)
    authority = repositories.authorities.get(f"authority-{record.request_id}")
    declaration = repositories.verifications.declaration_for_request(
        record.request_id,
    )
    if request is None or authority is None or record.remote_plan is None:
        raise RuntimeError("remote recovery acceptance inputs are missing")
    now = observed_at or datetime.now(UTC)
    payload = {
        "request": json.loads(dumps_document(request)),
        "authority": json.loads(dumps_document(authority)),
        "authority_active": authority.active_at(now),
        "plan": json.loads(dumps_document(snapshot.plan)),
        "remote_plan": json.loads(dumps_document(record.remote_plan)),
        "verification": (
            None if declaration is None else json.loads(dumps_document(declaration))
        ),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def classify_remote_failure(error: BaseException) -> RemoteAttemptFailure:
    message = str(error).lower()
    if any(word in message for word in ("policy", "privacy", "route changed")):
        return RemoteAttemptFailure.AUTHORITY_CHANGED
    if isinstance(error, TimeoutError):
        return RemoteAttemptFailure.TIMEOUT
    if isinstance(error, (EOFError, ConnectionError)):
        if "complete frame" in message or "partial" in message:
            return RemoteAttemptFailure.PARTIAL_RESULT
        return RemoteAttemptFailure.DISCONNECTED
    if isinstance(error, PermissionError):
        return RemoteAttemptFailure.AUTHENTICATION_FAILED
    if isinstance(error, OSError):
        return RemoteAttemptFailure.DISCONNECTED
    if isinstance(error, RuntimeError) and (
        "remote.execution" in message or "provider" in message
    ):
        return RemoteAttemptFailure.REMOTE_PROVIDER_FAILED
    return RemoteAttemptFailure.INVALID_RESULT


def local_retry_allowed(failure: RemoteAttemptFailure) -> bool:
    return failure in _RETRYABLE


def remote_attempt_reservation(
    record,
    acceptance_sha256: str,
    maximum_output_tokens: int,
) -> AttemptBudgetReservation:
    assert record.remote_plan is not None
    return AttemptBudgetReservation(
        f"budget-{record.request_id}-remote",
        record.instance_id,
        f"attempt-{record.request_id}-remote",
        AttemptKind.REMOTE,
        maximum_output_tokens,
        300_000,
        acceptance_sha256,
        record.remote_plan.plan_id,
    )


def local_recovery_reservation(
    record,
    acceptance_sha256: str,
) -> AttemptBudgetReservation:
    assert record.remote_plan is not None
    return AttemptBudgetReservation(
        f"budget-{record.request_id}-local-recovery",
        record.instance_id,
        f"attempt-{record.request_id}-local-recovery",
        AttemptKind.LOCAL_RECOVERY,
        1024,
        300_000,
        acceptance_sha256,
        record.remote_plan.plan_id,
    )


def pending_remote_recovery(
    record,
    failure: RemoteAttemptFailure,
    accepted_sha256: str,
    observed_sha256: str,
    remote_reservation: AttemptBudgetReservation,
    local_reservation: AttemptBudgetReservation,
    local_selection,
    detected_at: datetime,
) -> RemoteRecoveryEvidence:
    assert record.remote_plan is not None
    return RemoteRecoveryEvidence(
        f"remote-recovery-{record.request_id}",
        record.instance_id,
        record.request_id,
        record.remote_plan.plan_id,
        remote_reservation.reservation_id,
        remote_reservation.attempt_id,
        failure,
        accepted_sha256,
        observed_sha256,
        True,
        True,
        local_selection.selection_id,
        local_selection.model_ref,
        local_selection.tier,
        local_reservation.reservation_id,
        local_reservation.attempt_id,
        None,
        RemoteRecoveryDisposition.LOCAL_RETRY_PENDING,
        (f"remote.{failure.value}", "acceptance.unchanged", "fallback.local"),
        detected_at,
        None,
    )


def denied_remote_recovery(
    record,
    failure: RemoteAttemptFailure,
    accepted_sha256: str,
    observed_sha256: str,
    remote_reservation: AttemptBudgetReservation,
    reason_code: str,
    detected_at: datetime,
) -> RemoteRecoveryEvidence:
    assert record.remote_plan is not None
    return RemoteRecoveryEvidence(
        f"remote-recovery-{record.request_id}",
        record.instance_id,
        record.request_id,
        record.remote_plan.plan_id,
        remote_reservation.reservation_id,
        remote_reservation.attempt_id,
        failure,
        accepted_sha256,
        observed_sha256,
        accepted_sha256 == observed_sha256,
        False,
        None,
        None,
        None,
        None,
        None,
        None,
        RemoteRecoveryDisposition.RETRY_DENIED,
        (f"remote.{failure.value}", reason_code, "fallback.denied"),
        detected_at,
        detected_at,
    )


class RemoteAttemptRecoveryCoordinator:
    def __init__(
        self,
        repositories,
        selector,
        capacity,
        resident_models,
        budget_ledger_factory,
    ) -> None:
        self._repositories = repositories
        self._selector = selector
        self._capacity = capacity
        self._resident_models = resident_models
        self._budget_factory = budget_ledger_factory

    def reconcile_completed(self, running):
        remote = self._repositories.final_evidence.remote_execution_for_request(
            running.request_id,
        )
        if (
            remote is not None
            and remote.disposition
            is RemoteEvidenceDisposition.AUTHENTICATED_CANDIDATE
        ):
            return self._candidate_ready(running, remote.candidate_id)
        recovery = self._repositories.final_evidence.remote_recovery_for_request(
            running.request_id,
        )
        if (
            recovery is not None
            and recovery.disposition is RemoteRecoveryDisposition.RECOVERED
            and recovery.local_candidate_id is not None
        ):
            return self._candidate_ready(running, recovery.local_candidate_id)
        return None

    def reconcile_interrupted(self, running, snapshot):
        ledger = self._budget_factory(production_attempt_budget(running.instance_id))
        reservation = ledger.reservation(f"budget-{running.request_id}-remote")
        if reservation is None or reservation.acceptance_sha256 is None:
            raise RuntimeError("interrupted remote attempt lacks a bound reservation")
        return self.prepare_local_retry(
            running, snapshot, RemoteAttemptFailure.UNCERTAIN_COMPLETION,
            reservation,
        )

    def restore_local_selection(self, running, recovery):
        if running.selection.selection_id == recovery.local_selection_id:
            return running
        selection = self._select_local(running)
        if (
            selection.selection_id != recovery.local_selection_id
            or selection.model_ref != recovery.local_model_ref
            or selection.tier != recovery.local_expert_tier
        ):
            raise RuntimeError("local recovery selection changed after restart")
        return replace_execution(
            self._repositories, running, selection=selection,
        )

    def prepare_local_retry(self, running, snapshot, failure, reservation):
        accepted = reservation.acceptance_sha256
        if accepted is None:
            raise RuntimeError("remote attempt reservation lacks acceptance binding")
        observed = accepted_remote_contract_sha256(
            self._repositories, running, snapshot,
        )
        now = datetime.now(UTC)
        if not (local_retry_allowed(failure) and accepted == observed):
            reason = (
                "acceptance.changed"
                if accepted != observed else "failure.not_retryable"
            )
            return self._deny(
                running, snapshot, failure, accepted, observed,
                reservation, reason, now,
            )
        try:
            selection = self._select_local(running)
        except LookupError:
            return self._deny(
                running, snapshot, failure, accepted, observed,
                reservation, "fallback.unavailable", now,
            )
        local_reservation = local_recovery_reservation(running, accepted)
        ledger = self._budget_factory(production_attempt_budget(running.instance_id))
        existing = ledger.reservation(local_reservation.reservation_id)
        if existing is None and ledger.reserve(local_reservation) is None:
            return self._deny(
                running, snapshot, failure, accepted, observed,
                reservation, "fallback.budget_exhausted", now,
            )
        if existing is not None and existing != local_reservation:
            raise RuntimeError("local recovery reservation binding changed")
        evidence = pending_remote_recovery(
            running, failure, accepted, observed, reservation,
            local_reservation, selection, now,
        )
        current = self._repositories.final_evidence.remote_recovery_for_request(
            running.request_id,
        )
        if current is None:
            if not self._repositories.final_evidence.add_remote_recovery(evidence):
                raise RuntimeError("remote recovery evidence could not be recorded")
        elif current != evidence:
            raise RuntimeError("remote recovery evidence changed during reconciliation")
        return replace_execution(
            self._repositories, running, selection=selection,
            state=InferenceExecutionState.PREPARED, candidate_id=None,
            remote_attempt_consumed=True,
        )

    def fail_pending(self, request_id: str) -> None:
        recovery = self._repositories.final_evidence.remote_recovery_for_request(
            request_id,
        )
        if (
            recovery is not None
            and recovery.disposition
            is RemoteRecoveryDisposition.LOCAL_RETRY_PENDING
        ):
            self._repositories.final_evidence.fail_remote_recovery(
                request_id, datetime.now(UTC),
            )

    def _candidate_ready(self, running, candidate_id: str):
        candidate = self._repositories.final_evidence.candidate(candidate_id)
        if candidate is None or candidate.request_id != running.request_id:
            raise RuntimeError("reconciled candidate evidence is incomplete")
        return replace_execution(
            self._repositories, running,
            state=InferenceExecutionState.CANDIDATE_READY,
            candidate_id=candidate_id,
            remote_attempt_consumed=True,
        )

    def _select_local(self, running):
        declaration = self._repositories.verifications.declaration_for_request(
            running.request_id,
        )
        required_verifier_id = (
            None if declaration is None else declaration.contract.verifier_id
        )
        return self._selector.select(
            running.request_id, running.intent, self._capacity(),
            resident_model_refs=self._resident_models(),
            required_verifier_id=required_verifier_id,
        )

    def _deny(
        self,
        running,
        snapshot,
        failure,
        accepted,
        observed,
        reservation,
        reason,
        now,
    ):
        evidence = denied_remote_recovery(
            running, failure, accepted, observed, reservation, reason, now,
        )
        if not self._repositories.final_evidence.add_remote_recovery(evidence):
            raise RuntimeError("remote recovery evidence already exists")
        reference = PlanEvidenceReference(
            evidence.evidence_id, PlanEvidenceKind.REMOTE_RECOVERY, None,
        )
        advanced = PlanLifecycleService(self._repositories.plans).advance(
            snapshot.instance_id, snapshot.revision, StepOutcome.FAILED, (reference,),
        )
        if advanced.rejection is not None:
            raise RuntimeError("denied remote recovery could not terminate")
        return terminal_execution(
            self._repositories, running,
            failure_code="fabric.remote_recovery.denied",
        )
