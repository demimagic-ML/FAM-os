"""Cancellation, deadline, and degradation lifecycle commands."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.contracts import DegradationNotice
from fam_os.core.lifecycle.contracts import PlanInstanceSnapshot, PlanRejection
from fam_os.core.routing import RoutedTaskRequest


class ControlKind(StrEnum):
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    DEGRADED = "degraded"


class ControlRejection(StrEnum):
    INVALID_CONTEXT = "invalid_context"
    NOT_DUE = "not_due"
    REPLAYED = "replayed"


@dataclass(frozen=True, slots=True)
class PlanDeadlinePolicy:
    plan_id: str
    deadline: datetime

    def __post_init__(self) -> None:
        if not self.plan_id.strip():
            raise ValueError("plan_id must not be empty")
        if self.deadline.tzinfo is None or self.deadline.utcoffset() is None:
            raise ValueError("deadline must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ControlCommand:
    control_id: str
    plan_instance_id: str
    expected_revision: int
    routed: RoutedTaskRequest
    degradation: DegradationNotice | None = None

    def __post_init__(self) -> None:
        if not self.control_id.strip() or not self.plan_instance_id.strip():
            raise ValueError("control identifiers must not be empty")
        if not isinstance(self.expected_revision, int) or self.expected_revision < 0:
            raise ValueError("expected_revision must be nonnegative")
        if not isinstance(self.routed, RoutedTaskRequest):
            raise ValueError("control command requires routed evidence")


@dataclass(frozen=True, slots=True)
class ControlTransitionResult:
    plan_instance_id: str
    kind: ControlKind | None = None
    snapshot: PlanInstanceSnapshot | None = None
    degradation: DegradationNotice | None = None
    rejection: ControlRejection | PlanRejection | None = None

    def __post_init__(self) -> None:
        success = self.kind is not None and self.snapshot is not None and self.rejection is None
        rejected = self.kind is None and self.snapshot is None and self.rejection is not None
        if not (success or rejected):
            raise ValueError("control result requires success or rejection")
        if self.kind is ControlKind.DEGRADED and self.degradation is None:
            raise ValueError("degraded transition requires degradation evidence")
