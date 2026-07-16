"""Commands and outcomes for action confirmation and permission expiry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fam_os.applications import ActionConfirmation
from fam_os.core.lifecycle.contracts import PlanInstanceSnapshot, PlanRejection
from fam_os.core.routing import RoutedTaskRequest


class ConfirmationDisposition(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ConfirmationRejection(StrEnum):
    INVALID_CONTEXT = "invalid_context"
    INVALID_STEP = "invalid_step"
    INVALID_CONFIRMATION = "invalid_confirmation"
    PERMISSION_DENIED = "permission_denied"
    NOT_EXPIRED = "not_expired"
    REPLAYED = "replayed"


@dataclass(frozen=True, slots=True)
class ConfirmationCommand:
    plan_instance_id: str
    expected_revision: int
    routed: RoutedTaskRequest
    confirmation: ActionConfirmation

    def __post_init__(self) -> None:
        _require_command(self.plan_instance_id, self.expected_revision, self.routed)
        if not isinstance(self.confirmation, ActionConfirmation):
            raise ValueError("confirmation command requires typed confirmation")


@dataclass(frozen=True, slots=True)
class PermissionExpiryCommand:
    plan_instance_id: str
    expected_revision: int
    routed: RoutedTaskRequest

    def __post_init__(self) -> None:
        _require_command(self.plan_instance_id, self.expected_revision, self.routed)


@dataclass(frozen=True, slots=True)
class ConfirmationTransitionResult:
    plan_instance_id: str
    disposition: ConfirmationDisposition | None = None
    snapshot: PlanInstanceSnapshot | None = None
    confirmation: ActionConfirmation | None = None
    rejection: ConfirmationRejection | PlanRejection | None = None

    def __post_init__(self) -> None:
        success = self.disposition is not None and self.snapshot is not None
        rejected = self.rejection is not None and self.snapshot is None
        if success == rejected:
            raise ValueError("confirmation result requires success or rejection")
        if success and self.rejection is not None:
            raise ValueError("successful confirmation cannot carry rejection")
        needs_confirmation = self.disposition in {
            ConfirmationDisposition.APPROVED, ConfirmationDisposition.DENIED,
        }
        if success and needs_confirmation != (self.confirmation is not None):
            raise ValueError("confirmation evidence must match disposition")


def _require_command(instance_id, revision, routed) -> None:
    if not isinstance(instance_id, str) or not instance_id.strip():
        raise ValueError("plan_instance_id must not be empty")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise ValueError("expected_revision must be a nonnegative integer")
    if not isinstance(routed, RoutedTaskRequest):
        raise ValueError("command requires routed request evidence")
