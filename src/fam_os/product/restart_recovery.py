"""Restart-safe action state and fail-closed reconciliation policy."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol

from fam_os.applications import ActionProposal, ActionResult


RESTART_RECOVERY_VERSION = "fam.product.restart-recovery/v1alpha1"


class PersistedActionState(StrEnum):
    PREPARED = "prepared"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    INVOKING = "invoking"
    UNCERTAIN = "uncertain"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    VERIFIED = "verified"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RestartDisposition(StrEnum):
    REQUIRE_FRESH_APPROVAL = "require_fresh_approval"
    RECONCILE_POSTCONDITIONS = "reconcile_postconditions"
    RETAIN_TERMINAL = "retain_terminal"


@dataclass(frozen=True, slots=True)
class PersistedActionRecord:
    action_id: str
    plan_id: str
    idempotency_key: str
    proposal: ActionProposal
    state: PersistedActionState
    confirmation_id: str | None = None
    result: ActionResult | None = None
    contract_version: str = RESTART_RECOVERY_VERSION

    def __post_init__(self) -> None:
        if not all((self.action_id.strip(), self.plan_id.strip(), self.idempotency_key.strip())):
            raise ValueError("persisted action identity is invalid")
        if self.contract_version != RESTART_RECOVERY_VERSION:
            raise ValueError("unsupported restart recovery version")
        if self.state is PersistedActionState.APPROVED and self.confirmation_id is None:
            raise ValueError("approved action requires confirmation identity")
        terminal = self.state in {
            PersistedActionState.VERIFIED,
            PersistedActionState.FAILED,
            PersistedActionState.CANCELLED,
        }
        if terminal != (self.result is not None):
            raise ValueError("terminal action state and result disagree")


@dataclass(frozen=True, slots=True)
class RestartRecoveryDecision:
    action_id: str
    disposition: RestartDisposition
    previous_state: PersistedActionState
    resulting_state: PersistedActionState
    prior_confirmation_retained: bool
    provider_retry_allowed: bool = False
    contract_version: str = RESTART_RECOVERY_VERSION

    def __post_init__(self) -> None:
        if not self.action_id.strip() or self.provider_retry_allowed:
            raise ValueError("restart recovery never authorizes provider retry")
        if (
            self.disposition is RestartDisposition.REQUIRE_FRESH_APPROVAL
            and self.prior_confirmation_retained
        ):
            raise ValueError("fresh approval cannot retain prior confirmation")


def restart_decision(record: PersistedActionRecord) -> RestartRecoveryDecision:
    if record.state in _PENDING_APPROVAL_STATES:
        return RestartRecoveryDecision(
            record.action_id, RestartDisposition.REQUIRE_FRESH_APPROVAL,
            record.state, PersistedActionState.AWAITING_APPROVAL, False,
        )
    if record.state in _UNCERTAIN_STATES:
        return RestartRecoveryDecision(
            record.action_id, RestartDisposition.RECONCILE_POSTCONDITIONS,
            record.state, PersistedActionState.RECONCILIATION_REQUIRED, False,
        )
    return RestartRecoveryDecision(
        record.action_id, RestartDisposition.RETAIN_TERMINAL,
        record.state, record.state, record.confirmation_id is not None,
    )


class ActionPostconditionReconciler(Protocol):
    def reconcile(self, proposal: ActionProposal) -> ActionResult | None: ...


class StartupActionReconciler:
    def __init__(self, repository, postconditions: ActionPostconditionReconciler) -> None:
        self._repository = repository
        self._postconditions = postconditions

    def reconcile(self) -> tuple[RestartRecoveryDecision, ...]:
        return tuple(self._reconcile_one(record) for record in self._repository.recoverable())

    def _reconcile_one(self, record: PersistedActionRecord) -> RestartRecoveryDecision:
        decision = restart_decision(record)
        if decision.disposition is RestartDisposition.REQUIRE_FRESH_APPROVAL:
            replacement = replace(
                record,
                state=PersistedActionState.AWAITING_APPROVAL,
                confirmation_id=None,
            )
            if not self._repository.replace(record.state, replacement):
                raise RuntimeError("action changed during restart reconciliation")
            return decision
        if decision.disposition is RestartDisposition.RECONCILE_POSTCONDITIONS:
            reconciling = replace(
                record,
                state=PersistedActionState.RECONCILIATION_REQUIRED,
                confirmation_id=None,
            )
            if not self._repository.replace(record.state, reconciling):
                raise RuntimeError("action changed during restart reconciliation")
            result = self._postconditions.reconcile(record.proposal)
            if result is None:
                return decision
            final_state = (
                PersistedActionState.VERIFIED if result.verified
                else PersistedActionState.FAILED
            )
            terminal = replace(reconciling, state=final_state, result=result)
            if not self._repository.replace(reconciling.state, terminal):
                raise RuntimeError("action changed while postconditions were checked")
            return replace(decision, resulting_state=final_state)
        return decision


_PENDING_APPROVAL_STATES = {
    PersistedActionState.PREPARED,
    PersistedActionState.AWAITING_APPROVAL,
    PersistedActionState.APPROVED,
}
_UNCERTAIN_STATES = {
    PersistedActionState.INVOKING,
    PersistedActionState.UNCERTAIN,
    PersistedActionState.RECONCILIATION_REQUIRED,
}
