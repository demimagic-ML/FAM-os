"""Immutable state and outcomes for the generic Core plan lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.contracts import (
    ExecutionPlan,
    PlanStepKind,
    StepOutcome,
    TerminalDisposition,
)


class PlanEventKind(StrEnum):
    STARTED = "started"
    TRANSITIONED = "transitioned"


class PlanRejection(StrEnum):
    INVALID_BINDING = "invalid_binding"
    ALREADY_STARTED = "already_started"
    NOT_FOUND = "not_found"
    REVISION_CONFLICT = "revision_conflict"
    TERMINAL = "terminal"
    ILLEGAL_OUTCOME = "illegal_outcome"


class PlanEvidenceKind(StrEnum):
    OBSERVATION = "observation"
    ACTION_PROPOSAL = "action_proposal"
    ACTION_CONFIRMATION = "action_confirmation"
    ACTION_RESULT = "action_result"
    ACTION_AUDIT = "action_audit"
    PERMISSION_EXPIRY = "permission_expiry"
    FAILED_ATTEMPT = "failed_attempt"
    REPAIR_ATTEMPT = "repair_attempt"
    ESCALATION_ATTEMPT = "escalation_attempt"
    CANCELLATION = "cancellation"
    TIMEOUT = "timeout"
    DEGRADATION = "degradation"
    RELEASE_CANDIDATE = "release_candidate"
    VERIFICATION_PASS = "verification_pass"


@dataclass(frozen=True, slots=True)
class PlanEvidenceReference:
    reference_id: str
    kind: PlanEvidenceKind
    capability_id: str | None
    permission_grant_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.reference_id, "reference_id")
        if not isinstance(self.kind, PlanEvidenceKind):
            raise ValueError("evidence kind must be a PlanEvidenceKind")
        application_kinds = {
            PlanEvidenceKind.OBSERVATION,
            PlanEvidenceKind.ACTION_PROPOSAL,
            PlanEvidenceKind.ACTION_CONFIRMATION,
            PlanEvidenceKind.ACTION_RESULT,
            PlanEvidenceKind.ACTION_AUDIT,
            PlanEvidenceKind.PERMISSION_EXPIRY,
        }
        if self.kind in application_kinds:
            _require_text(self.capability_id, "capability_id")
            _require_text(self.permission_grant_id, "permission_grant_id")
        elif self.kind in {
            PlanEvidenceKind.FAILED_ATTEMPT,
            PlanEvidenceKind.REPAIR_ATTEMPT,
            PlanEvidenceKind.ESCALATION_ATTEMPT,
        }:
            _require_text(self.capability_id, "capability_id")
        elif self.permission_grant_id is not None:
            raise ValueError("non-application evidence cannot carry an application grant")


@dataclass(frozen=True, slots=True)
class PlanAuthorityBinding:
    admission_id: str
    valid_until: datetime

    def __post_init__(self) -> None:
        _require_text(self.admission_id, "admission_id")
        _require_aware(self.valid_until)


@dataclass(frozen=True, slots=True)
class PlanLifecycleEvent:
    event_id: str
    revision: int
    occurred_at: datetime
    kind: PlanEventKind
    target_step_id: str
    source_step_id: str | None = None
    outcome: StepOutcome | None = None
    terminal_disposition: TerminalDisposition | None = None
    evidence_refs: tuple[PlanEvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PlanEventKind):
            raise ValueError("event kind must be a PlanEventKind")
        if self.outcome is not None and not isinstance(self.outcome, StepOutcome):
            raise ValueError("event outcome must be a StepOutcome")
        if self.terminal_disposition is not None and not isinstance(
            self.terminal_disposition, TerminalDisposition
        ):
            raise ValueError("event terminal disposition is invalid")
        if not all(isinstance(item, PlanEvidenceReference) for item in self.evidence_refs):
            raise ValueError("event evidence must contain typed references")
        if len({item.reference_id for item in self.evidence_refs}) != len(self.evidence_refs):
            raise ValueError("event evidence references must be unique")
        _require_text(self.event_id, "event_id")
        _require_text(self.target_step_id, "target_step_id")
        _require_aware(self.occurred_at)
        if self.revision < 0:
            raise ValueError("event revision must not be negative")
        if self.kind is PlanEventKind.STARTED:
            if self.revision or self.source_step_id is not None or self.outcome is not None:
                raise ValueError("started event must be initial and have no outcome")
            if self.evidence_refs:
                raise ValueError("started event cannot carry evidence")
        elif self.source_step_id is None or self.outcome is None or not self.revision:
            raise ValueError("transition event requires source, outcome, and revision")
        else:
            _require_text(self.source_step_id, "source_step_id")


@dataclass(frozen=True, slots=True)
class PlanInstanceSnapshot:
    instance_id: str
    plan: ExecutionPlan
    current_step_id: str
    revision: int
    events: tuple[PlanLifecycleEvent, ...]
    terminal_disposition: TerminalDisposition | None = None
    authority_binding: PlanAuthorityBinding | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.plan, ExecutionPlan):
            raise ValueError("snapshot plan must be an ExecutionPlan")
        if not isinstance(self.authority_binding, PlanAuthorityBinding):
            raise ValueError("snapshot requires an authority binding")
        _require_text(self.instance_id, "instance_id")
        _validate_event_log(self)
        step = _step(self.plan, self.current_step_id)
        if step.terminal_disposition is not self.terminal_disposition:
            raise ValueError("snapshot terminal disposition must match current step")

    @property
    def terminal(self) -> bool:
        return self.terminal_disposition is not None


@dataclass(frozen=True, slots=True)
class PlanStartResult:
    request_id: str
    snapshot: PlanInstanceSnapshot | None = None
    rejection: PlanRejection | None = None

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_rejection(self.rejection)
        _require_one(self.snapshot, self.rejection, "start result")


@dataclass(frozen=True, slots=True)
class PlanAdvanceResult:
    instance_id: str
    snapshot: PlanInstanceSnapshot | None = None
    rejection: PlanRejection | None = None

    def __post_init__(self) -> None:
        _require_text(self.instance_id, "instance_id")
        _require_rejection(self.rejection)
        _require_one(self.snapshot, self.rejection, "advance result")


def _validate_event_log(snapshot: PlanInstanceSnapshot) -> None:
    if snapshot.revision < 0 or len(snapshot.events) != snapshot.revision + 1:
        raise ValueError("snapshot revision must match event count")
    if len({event.event_id for event in snapshot.events}) != len(snapshot.events):
        raise ValueError("plan event IDs must be unique")
    first = snapshot.events[0]
    if first.kind is not PlanEventKind.STARTED or first.target_step_id != snapshot.plan.entry_step_id:
        raise ValueError("event log must start at the plan entry step")
    _require_event_target(snapshot.plan, first)
    current = first.target_step_id
    for revision, event in enumerate(snapshot.events[1:], start=1):
        if event.revision != revision or event.source_step_id != current:
            raise ValueError("event log revisions and sources must be contiguous")
        _require_event_target(snapshot.plan, event)
        _require_event_evidence(snapshot.plan, event)
        current = _transition_target(snapshot.plan, current, event.outcome, event.target_step_id)
    if current != snapshot.current_step_id:
        raise ValueError("event log must end at the current step")


def _transition_target(plan, source, outcome, target) -> str:
    matches = tuple(
        transition for transition in plan.transitions
        if transition.source_step_id == source and transition.outcome is outcome
    )
    if len(matches) != 1 or matches[0].target_step_id != target:
        raise ValueError("event log contains an illegal plan transition")
    return target


def _require_event_target(plan, event) -> None:
    if _step(plan, event.target_step_id).terminal_disposition is not event.terminal_disposition:
        raise ValueError("event terminal disposition must match its target step")


def _require_event_evidence(plan, event) -> None:
    source = _step(plan, event.source_step_id)
    expected = {
        PlanEvidenceKind.OBSERVATION: PlanStepKind.OBSERVE,
        PlanEvidenceKind.ACTION_PROPOSAL: PlanStepKind.PREPARE_ACTION,
        PlanEvidenceKind.ACTION_CONFIRMATION: PlanStepKind.CONFIRM_ACTION,
        PlanEvidenceKind.ACTION_RESULT: PlanStepKind.EXECUTE_ACTION,
        PlanEvidenceKind.ACTION_AUDIT: PlanStepKind.EXECUTE_ACTION,
        PlanEvidenceKind.PERMISSION_EXPIRY: PlanStepKind.CONFIRM_ACTION,
    }
    for reference in event.evidence_refs:
        if reference.kind in {
            PlanEvidenceKind.CANCELLATION,
            PlanEvidenceKind.TIMEOUT,
            PlanEvidenceKind.DEGRADATION,
        }:
            if reference.capability_id is not None:
                if reference.capability_id not in plan.route.required_capabilities:
                    raise ValueError("control evidence capability must be routed")
            continue
        if reference.kind in {
            PlanEvidenceKind.RELEASE_CANDIDATE,
            PlanEvidenceKind.VERIFICATION_PASS,
        }:
            target = _step(plan, event.target_step_id)
            if target.terminal_disposition is not TerminalDisposition.RELEASE:
                raise ValueError("release evidence must target release terminal")
            if reference.capability_id is not None:
                if reference.capability_id not in plan.route.required_capabilities:
                    raise ValueError("release evidence capability must be routed")
            continue
        if reference.kind in {
            PlanEvidenceKind.FAILED_ATTEMPT,
            PlanEvidenceKind.REPAIR_ATTEMPT,
            PlanEvidenceKind.ESCALATION_ATTEMPT,
        }:
            target = _step(plan, event.target_step_id)
            if target.kind is not PlanStepKind.INFERENCE:
                raise ValueError("attempt evidence must enter an inference step")
            if reference.capability_id not in target.capability_ids:
                raise ValueError("attempt capability must belong to target step")
            continue
        if source.kind is not expected[reference.kind]:
            raise ValueError("evidence kind must match source step kind")
        if reference.capability_id not in source.capability_ids:
            raise ValueError("evidence capability must belong to source step")


def _step(plan: ExecutionPlan, step_id: str):
    for step in plan.steps:
        if step.step_id == step_id:
            return step
    raise ValueError("snapshot current step must exist in the plan")


def _require_one(value, rejection, label: str) -> None:
    if (value is None) == (rejection is None):
        raise ValueError(f"{label} requires exactly one outcome")


def _require_rejection(rejection) -> None:
    if rejection is not None and not isinstance(rejection, PlanRejection):
        raise ValueError("result rejection must be a PlanRejection")


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{field_name} must be strict nonempty text")


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("event time must be timezone-aware")
