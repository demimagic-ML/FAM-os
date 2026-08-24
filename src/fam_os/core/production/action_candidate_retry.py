"""Budgeted regeneration of structurally invalid application candidates."""

from dataclasses import dataclass

from fam_os.core.lifecycle.attempt_contracts import AttemptKind
from fam_os.core.lifecycle.global_budget import AttemptBudgetReservation
from fam_os.core.production.attempt_budget import production_attempt_budget
from fam_os.core.production.contracts import (
    InferenceExecutionRecord,
    InferenceExecutionState,
)
from fam_os.core.production.execution_state import replace_execution


@dataclass(frozen=True, slots=True)
class ActionCandidateRetryPreparation:
    record: InferenceExecutionRecord
    maximum_output_tokens: int


class ActionCandidateRetry:
    """Reserve one repair and one strong escalation in the plan-global budget."""

    def __init__(
        self, repositories, selector, capacity, resident_models,
        budget_ledger_factory,
    ) -> None:
        self._repositories = repositories
        self._selector = selector
        self._capacity = capacity
        self._resident_models = resident_models
        self._budget_factory = budget_ledger_factory

    def prepare(
        self, record: InferenceExecutionRecord, feedback: str, *, escalation: bool,
    ) -> ActionCandidateRetryPreparation | None:
        label = "parameter-escalation" if escalation else "parameter-repair"
        kind = AttemptKind.ESCALATION if escalation else AttemptKind.REPAIR
        reservation = AttemptBudgetReservation(
            f"budget-{record.request_id}-{label}", record.instance_id,
            f"attempt-{record.request_id}-{label}", kind, 2048,
            180_000 if escalation else 60_000,
        )
        ledger = self._budget_factory(production_attempt_budget(record.instance_id))
        if ledger.reserve(reservation) is None:
            return None
        selection = record.selection
        if escalation:
            declaration = self._repositories.verifications.declaration_for_request(
                record.request_id,
            )
            required_verifier = (
                None if declaration is None else declaration.contract.verifier_id
            )
            try:
                selection = self._selector.select(
                    record.request_id, record.intent, self._capacity(), escalation=True,
                    resident_model_refs=self._resident_models(),
                    excluded_model_refs=(record.selection.model_ref,),
                    required_verifier_id=required_verifier,
                )
            except LookupError:
                return None
        prepared = replace_execution(
            self._repositories, record, selection=selection,
            state=InferenceExecutionState.PREPARED, candidate_id=None,
            verifier_feedback=feedback,
        )
        return ActionCandidateRetryPreparation(prepared, reservation.reserved_tokens)
