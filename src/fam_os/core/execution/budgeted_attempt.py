"""Global-budget enforcing decorator for repair and escalation attempts."""

from dataclasses import dataclass

from fam_os.core.execution.contracts import AttemptKind
from fam_os.core.execution.errors import ExecutionConfigurationError
from fam_os.core.lifecycle.attempt_contracts import AttemptKind as BudgetAttemptKind
from fam_os.core.lifecycle.global_budget import (
    AttemptBudgetReservation,
    InMemoryGlobalAttemptBudgetLedger,
)


@dataclass(slots=True)
class BudgetedAttemptExecutor:
    delegate: object
    ledger: InMemoryGlobalAttemptBudgetLedger
    maximum_attempt_wall_milliseconds: int

    def execute(self, attempt_id, kind, expert, placement, messages, settings):
        budget_kind = _budget_kind(kind)
        if budget_kind is not None:
            reservation = AttemptBudgetReservation(
                f"budget:{attempt_id}", self.ledger.budget.plan_instance_id,
                attempt_id, budget_kind, settings.max_output_tokens,
                self.maximum_attempt_wall_milliseconds,
            )
            if self.ledger.reserve(reservation) is None:
                raise ExecutionConfigurationError("global repair/escalation budget exhausted")
        return self.delegate.execute(attempt_id, kind, expert, placement, messages, settings)


def _budget_kind(kind: AttemptKind) -> BudgetAttemptKind | None:
    if kind is AttemptKind.REPAIR or kind is AttemptKind.ESCALATION_REPAIR:
        return BudgetAttemptKind.REPAIR
    if kind is AttemptKind.ESCALATION:
        return BudgetAttemptKind.ESCALATION
    return None
