"""Trusted policy and evidence for bounded repair and escalation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fam_os.core.lifecycle.contracts import PlanInstanceSnapshot, PlanRejection
from fam_os.core.routing import RoutedTaskRequest


class AttemptKind(StrEnum):
    REPAIR = "repair"
    ESCALATION = "escalation"


class AttemptRejection(StrEnum):
    INVALID_CONTEXT = "invalid_context"
    INVALID_STEP = "invalid_step"
    BUDGET_EXHAUSTED = "budget_exhausted"
    REPLAYED = "replayed"


@dataclass(frozen=True, slots=True)
class AttemptBudgetPolicy:
    plan_id: str
    repair_step_ids: tuple[str, ...]
    escalation_step_ids: tuple[str, ...]
    max_repairs: int
    max_escalations: int

    def __post_init__(self) -> None:
        _text(self.plan_id, "plan_id")
        _unique(self.repair_step_ids, "repair_step_ids")
        _unique(self.escalation_step_ids, "escalation_step_ids")
        if set(self.repair_step_ids) & set(self.escalation_step_ids):
            raise ValueError("repair and escalation steps must be distinct")
        for name in ("max_repairs", "max_escalations"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.max_repairs > len(self.repair_step_ids):
            raise ValueError("repair budget exceeds unrolled repair steps")
        if self.max_escalations > len(self.escalation_step_ids):
            raise ValueError("escalation budget exceeds unrolled escalation steps")


@dataclass(frozen=True, slots=True)
class AttemptTransitionCommand:
    plan_instance_id: str
    expected_revision: int
    routed: RoutedTaskRequest
    failed_attempt_id: str
    next_attempt_id: str

    def __post_init__(self) -> None:
        for name in ("plan_instance_id", "failed_attempt_id", "next_attempt_id"):
            _text(getattr(self, name), name)
        if self.failed_attempt_id == self.next_attempt_id:
            raise ValueError("failed and next attempt IDs must differ")
        if not isinstance(self.expected_revision, int) or self.expected_revision < 0:
            raise ValueError("expected_revision must be nonnegative")
        if not isinstance(self.routed, RoutedTaskRequest):
            raise ValueError("attempt transition requires routed evidence")


@dataclass(frozen=True, slots=True)
class AttemptTransitionResult:
    plan_instance_id: str
    kind: AttemptKind | None = None
    snapshot: PlanInstanceSnapshot | None = None
    rejection: AttemptRejection | PlanRejection | None = None

    def __post_init__(self) -> None:
        success = self.kind is not None and self.snapshot is not None and self.rejection is None
        rejected = self.kind is None and self.snapshot is None and self.rejection is not None
        if not (success or rejected):
            raise ValueError("attempt result requires success or rejection")


def _unique(values, field_name) -> None:
    for value in values:
        _text(value, field_name)
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must be unique")


def _text(value, field_name) -> None:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{field_name} must be strict nonempty text")
