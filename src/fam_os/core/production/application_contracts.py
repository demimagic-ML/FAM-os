"""Durable orchestration state for capability-driven application tasks."""

from dataclasses import dataclass
from enum import StrEnum

from fam_os.applications import (
    ActionConfirmation,
    ActionProposal,
    ActionResult,
    ObservationResult,
)
from fam_os.core.routing import RoutedTaskRequest


APPLICATION_EXECUTION_VERSION = "fam.core.application-execution/v1alpha1"


class ApplicationExecutionState(StrEnum):
    ACTIVE = "active"
    WAITING_APPROVAL = "waiting_approval"
    RECOVERY_REQUIRED = "recovery_required"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class ApplicationExecutionRecord:
    instance_id: str
    request_id: str
    routed: RoutedTaskRequest
    application_instance_id: str
    resource_uri: str | None
    permission_grant_id: str
    state: ApplicationExecutionState
    revision: int
    observations: tuple[ObservationResult, ...] = ()
    proposal: ActionProposal | None = None
    confirmation: ActionConfirmation | None = None
    action_result: ActionResult | None = None
    reversal_source_session_id: str | None = None
    reversal_session_id: str | None = None
    contract_version: str = APPLICATION_EXECUTION_VERSION

    def __post_init__(self) -> None:
        for name in (
            "instance_id", "request_id", "application_instance_id",
            "permission_grant_id",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be nonempty")
        if self.routed.request_id != self.request_id:
            raise ValueError("application execution request does not match routing")
        if self.revision < 0 or isinstance(self.revision, bool):
            raise ValueError("application execution revision is invalid")
        if self.contract_version != APPLICATION_EXECUTION_VERSION:
            raise ValueError("application execution version is unsupported")
        if self.state in {
            ApplicationExecutionState.WAITING_APPROVAL,
            ApplicationExecutionState.RECOVERY_REQUIRED,
        } and self.proposal is None:
            raise ValueError("approval or recovery state requires an action proposal")
        if self.confirmation is not None and self.proposal is None:
            raise ValueError("application confirmation requires a proposal")
        if self.action_result is not None and self.proposal is None:
            raise ValueError("application result requires a proposal")
        for name in ("reversal_source_session_id", "reversal_session_id"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be nonempty when present")
            if value == self.instance_id:
                raise ValueError(f"{name} cannot reference the same execution")
