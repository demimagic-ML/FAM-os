"""Bounded attempt composition for verified parity runs."""

from fam_os.core.execution import BudgetedAttemptExecutor
from fam_os.core.execution.attempt import AttemptExecutor
from fam_os.core.lifecycle import GlobalAttemptBudget, InMemoryGlobalAttemptBudgetLedger


def budgeted_attempts(service, fixture, verifier):
    attempts = AttemptExecutor(service.runtime, verifier)
    attempt_count = fixture.repair_attempts + fixture.escalation_repair_attempts
    if fixture.escalate_on_failure:
        attempt_count += 1
    ledger = InMemoryGlobalAttemptBudgetLedger(GlobalAttemptBudget(
        "verified-parity-plan", fixture.max_output_tokens * attempt_count,
        int(fixture.timeout_seconds * 1000) * attempt_count,
        fixture.repair_attempts + fixture.escalation_repair_attempts,
        1 if fixture.escalate_on_failure else 0,
    ))
    executor = BudgetedAttemptExecutor(
        attempts, ledger, int(fixture.timeout_seconds * 1000),
    )
    return executor, ledger
