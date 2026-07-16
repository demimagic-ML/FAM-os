"""Atomic plan-global repair and escalation time/token budget ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from fam_os.core.lifecycle.attempt_contracts import AttemptKind


GLOBAL_ATTEMPT_BUDGET_VERSION = "fam.core.global-attempt-budget/v1alpha1"


@dataclass(frozen=True, slots=True)
class GlobalAttemptBudget:
    plan_instance_id: str
    maximum_tokens: int
    maximum_wall_milliseconds: int
    maximum_repairs: int
    maximum_escalations: int
    contract_version: str = GLOBAL_ATTEMPT_BUDGET_VERSION

    def __post_init__(self) -> None:
        if not self.plan_instance_id.strip():
            raise ValueError("plan_instance_id must not be empty")
        values = (self.maximum_tokens, self.maximum_wall_milliseconds, self.maximum_repairs, self.maximum_escalations)
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
            raise ValueError("global attempt budgets must be nonnegative integers")


@dataclass(frozen=True, slots=True)
class AttemptBudgetReservation:
    reservation_id: str
    plan_instance_id: str
    attempt_id: str
    kind: AttemptKind
    reserved_tokens: int
    reserved_wall_milliseconds: int

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (
            self.reservation_id, self.plan_instance_id, self.attempt_id,
        )):
            raise ValueError("budget reservation IDs must not be empty")
        if self.reserved_tokens <= 0 or self.reserved_wall_milliseconds <= 0:
            raise ValueError("budget reservations must be positive")


@dataclass(frozen=True, slots=True)
class GlobalAttemptBudgetSnapshot:
    plan_instance_id: str
    consumed_tokens: int
    consumed_wall_milliseconds: int
    repairs: int
    escalations: int
    reservation_ids: tuple[str, ...]
    contract_version: str = GLOBAL_ATTEMPT_BUDGET_VERSION


@dataclass(slots=True)
class InMemoryGlobalAttemptBudgetLedger:
    budget: GlobalAttemptBudget
    _reservations: dict[str, AttemptBudgetReservation] = field(default_factory=dict)
    _attempt_ids: set[str] = field(default_factory=set)
    _lock: RLock = field(default_factory=RLock)

    def reserve(self, reservation: AttemptBudgetReservation) -> GlobalAttemptBudgetSnapshot | None:
        with self._lock:
            if not self._valid_new(reservation):
                return None
            current = self.snapshot()
            repairs = current.repairs + (reservation.kind is AttemptKind.REPAIR)
            escalations = current.escalations + (reservation.kind is AttemptKind.ESCALATION)
            if (
                current.consumed_tokens + reservation.reserved_tokens > self.budget.maximum_tokens
                or current.consumed_wall_milliseconds + reservation.reserved_wall_milliseconds > self.budget.maximum_wall_milliseconds
                or repairs > self.budget.maximum_repairs
                or escalations > self.budget.maximum_escalations
            ):
                return None
            self._reservations[reservation.reservation_id] = reservation
            self._attempt_ids.add(reservation.attempt_id)
            return self.snapshot()

    def snapshot(self) -> GlobalAttemptBudgetSnapshot:
        with self._lock:
            values = tuple(self._reservations.values())
            return GlobalAttemptBudgetSnapshot(
                self.budget.plan_instance_id,
                sum(item.reserved_tokens for item in values),
                sum(item.reserved_wall_milliseconds for item in values),
                sum(item.kind is AttemptKind.REPAIR for item in values),
                sum(item.kind is AttemptKind.ESCALATION for item in values),
                tuple(sorted(self._reservations)),
            )

    def _valid_new(self, reservation) -> bool:
        return (
            reservation.plan_instance_id == self.budget.plan_instance_id
            and bool(reservation.reservation_id.strip())
            and bool(reservation.attempt_id.strip())
            and reservation.reservation_id not in self._reservations
            and reservation.attempt_id not in self._attempt_ids
            and reservation.reserved_tokens > 0
            and reservation.reserved_wall_milliseconds > 0
        )
