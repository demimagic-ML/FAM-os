"""Commands and outcomes for confirmed application-action execution."""

from dataclasses import dataclass
from enum import StrEnum

from fam_os.applications import (
    ActionConfirmation, ActionProposal, ActionResult, ConditionEvidence, Reversibility,
)
from fam_os.core.lifecycle.contracts import PlanInstanceSnapshot, PlanRejection
from fam_os.core.routing import RoutedTaskRequest


class ActionExecutionRejection(StrEnum):
    INVALID_CONTEXT = "invalid_context"
    INVALID_STEP = "invalid_step"
    INVALID_EVIDENCE = "invalid_evidence"
    PERMISSION_DENIED = "permission_denied"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    AUDIT_UNAVAILABLE = "audit_unavailable"
    REPLAYED = "replayed"


@dataclass(frozen=True, slots=True)
class ActionExecutionCommand:
    plan_instance_id: str
    expected_revision: int
    routed: RoutedTaskRequest
    proposal: ActionProposal
    confirmation: ActionConfirmation

    def __post_init__(self) -> None:
        if not self.plan_instance_id.strip():
            raise ValueError("action execution plan ID must not be empty")
        if isinstance(self.expected_revision, bool) or self.expected_revision < 0:
            raise ValueError("action execution revision must be nonnegative")


@dataclass(frozen=True, slots=True)
class ActionRecoveryMetadata:
    reversibility: Reversibility
    reversal_capability_id: str | None = None
    reversal_token: str | None = None
    compensation_required: bool = False

    def __post_init__(self) -> None:
        recoverable = self.reversibility in (
            Reversibility.REVERSIBLE, Reversibility.COMPENSATABLE,
        )
        if recoverable:
            if self.reversal_capability_id is None:
                raise ValueError("recoverable action requires recovery capability")
        elif self.reversal_capability_id is not None or self.reversal_token is not None:
            raise ValueError("irreversible action cannot expose reversal metadata")
        if self.reversal_token is not None and self.reversal_capability_id is None:
            raise ValueError("reversal token requires a capability")


@dataclass(frozen=True, slots=True)
class ActionExecutionResult:
    plan_instance_id: str
    operation_id: str
    provider_invoked: bool
    audit_event_ids: tuple[str, ...] = ()
    precondition_evidence: tuple[ConditionEvidence, ...] = ()
    action_result: ActionResult | None = None
    recovery: ActionRecoveryMetadata | None = None
    snapshot: PlanInstanceSnapshot | None = None
    rejection: ActionExecutionRejection | PlanRejection | None = None

    def __post_init__(self) -> None:
        if not self.plan_instance_id.strip() or not self.operation_id.strip():
            raise ValueError("action execution result identity is invalid")
        if len(set(self.audit_event_ids)) != len(self.audit_event_ids):
            raise ValueError("action audit event IDs must be unique")
        if self.rejection is None:
            if self.action_result is None or self.snapshot is None or self.recovery is None:
                raise ValueError("completed action execution requires result and snapshot")
        elif not self.provider_invoked:
            if self.action_result is not None or self.snapshot is not None or self.recovery is not None:
                raise ValueError("pre-provider rejection cannot claim action state")
