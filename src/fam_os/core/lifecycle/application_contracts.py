"""Transient inputs and results for application-backed plan steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from fam_os.applications import ActionProposal, ObservationResult
from fam_os.core.lifecycle.contracts import PlanInstanceSnapshot, PlanRejection
from fam_os.core.routing import RoutedTaskRequest


class ApplicationStepRejection(StrEnum):
    INVALID_CONTEXT = "invalid_context"
    INVALID_STEP = "invalid_step"
    PERMISSION_DENIED = "permission_denied"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_EVIDENCE = "invalid_evidence"


@dataclass(frozen=True, slots=True)
class ObservationAcquisition:
    plan_instance_id: str
    expected_revision: int
    routed: RoutedTaskRequest
    application_instance_id: str
    permission_grant_id: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    resource_uri: str | None = None

    def __post_init__(self) -> None:
        _require_command(self.plan_instance_id, self.expected_revision, self.routed)


@dataclass(frozen=True, slots=True)
class ActionProposalAcquisition:
    plan_instance_id: str
    expected_revision: int
    routed: RoutedTaskRequest
    application_instance_id: str
    permission_grant_id: str
    summary: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    resource_uri: str | None = None
    expected_resource_revision: str | None = None

    def __post_init__(self) -> None:
        _require_command(self.plan_instance_id, self.expected_revision, self.routed)
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValueError("action proposal summary must not be empty")


@dataclass(frozen=True, slots=True)
class ApplicationStepResult:
    plan_instance_id: str
    snapshot: PlanInstanceSnapshot | None = None
    evidence: ObservationResult | ActionProposal | None = None
    rejection: ApplicationStepRejection | PlanRejection | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.plan_instance_id, str) or not self.plan_instance_id.strip():
            raise ValueError("plan_instance_id must not be empty")
        valid_evidence = self.evidence is None or isinstance(
            self.evidence, (ObservationResult, ActionProposal)
        )
        valid_rejection = self.rejection is None or isinstance(
            self.rejection, (ApplicationStepRejection, PlanRejection)
        )
        if not valid_evidence or not valid_rejection:
            raise ValueError("application step result contains invalid evidence")
        succeeded = (
            self.snapshot is not None
            and self.evidence is not None
            and self.rejection is None
        )
        rejected = (
            self.snapshot is None
            and self.evidence is None
            and self.rejection is not None
        )
        if not (succeeded or rejected):
            raise ValueError("application step result requires success or rejection")


def _require_command(instance_id, revision, routed) -> None:
    if not isinstance(instance_id, str) or not instance_id.strip():
        raise ValueError("plan_instance_id must not be empty")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise ValueError("expected_revision must be a nonnegative integer")
    if not isinstance(routed, RoutedTaskRequest):
        raise ValueError("command requires routed request evidence")
