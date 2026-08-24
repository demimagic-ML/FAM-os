"""Owner-visible controls for live production adaptation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


LIVE_ADAPTATION_CONTROL_VERSION = "fam.adaptation.live-control/v1alpha1"


class AdaptationControlOperation(StrEnum):
    ENABLE = "enable"
    DISABLE = "disable"
    RESET = "reset"
    EVALUATE = "evaluate"
    ROLLBACK = "rollback"


class AdaptationControlStatus(StrEnum):
    APPLIED = "applied"
    NO_CHANGE = "no_change"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class WorkflowAdaptationSelection:
    workflow_id: str
    snapshot_id: str

    def __post_init__(self) -> None:
        _text(self.workflow_id, "workflow_id")
        _text(self.snapshot_id, "snapshot_id")


@dataclass(frozen=True, slots=True)
class LiveAdaptationControlState:
    revision: int
    enabled: bool
    active_selections: tuple[WorkflowAdaptationSelection, ...]
    known_good_selections: tuple[WorkflowAdaptationSelection, ...]
    drifted_snapshot_ids: tuple[str, ...]
    updated_at: datetime
    last_operation: AdaptationControlOperation | None = None
    local_only: bool = True
    contract_version: str = LIVE_ADAPTATION_CONTROL_VERSION

    def __post_init__(self) -> None:
        if isinstance(self.revision, bool) or self.revision < 0:
            raise ValueError("adaptation control revision must be nonnegative")
        _selections(self.active_selections, "active")
        _selections(self.known_good_selections, "known-good")
        if len(set(self.drifted_snapshot_ids)) != len(self.drifted_snapshot_ids):
            raise ValueError("drifted adaptation snapshots must be unique")
        for snapshot_id in self.drifted_snapshot_ids:
            _text(snapshot_id, "drifted_snapshot_id")
        selected = {
            item.snapshot_id
            for item in (*self.active_selections, *self.known_good_selections)
        }
        if selected & set(self.drifted_snapshot_ids):
            raise ValueError("drifted adaptation snapshots cannot remain selected")
        _time(self.updated_at)
        if not self.local_only:
            raise ValueError("adaptation control state must remain local")
        if self.contract_version != LIVE_ADAPTATION_CONTROL_VERSION:
            raise ValueError("unsupported live adaptation control version")


@dataclass(frozen=True, slots=True)
class LiveAdaptationControlRequest:
    request_id: str
    operation: AdaptationControlOperation
    confirmed: bool
    target_workflow_id: str | None = None
    contract_version: str = LIVE_ADAPTATION_CONTROL_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        if not isinstance(self.operation, AdaptationControlOperation):
            raise ValueError("adaptation control operation is invalid")
        targeted = self.operation in {
            AdaptationControlOperation.EVALUATE,
            AdaptationControlOperation.ROLLBACK,
        }
        if targeted != (self.target_workflow_id is not None):
            raise ValueError("adaptation control target does not match operation")
        if self.target_workflow_id is not None:
            _text(self.target_workflow_id, "target_workflow_id")
        if self.contract_version != LIVE_ADAPTATION_CONTROL_VERSION:
            raise ValueError("unsupported live adaptation control version")


@dataclass(frozen=True, slots=True)
class LiveAdaptationControlReceipt:
    receipt_id: str
    request_id: str
    operation: AdaptationControlOperation
    status: AdaptationControlStatus
    created_at: datetime
    before_revision: int
    state: LiveAdaptationControlState
    target_workflow_id: str | None
    removed_learning_count: int
    removed_snapshot_count: int
    removed_prewarm_count: int
    reason_codes: tuple[str, ...]
    local_only: bool = True
    contract_version: str = LIVE_ADAPTATION_CONTROL_VERSION

    def __post_init__(self) -> None:
        _text(self.receipt_id, "receipt_id")
        _text(self.request_id, "request_id")
        if not isinstance(self.operation, AdaptationControlOperation):
            raise ValueError("adaptation receipt operation is invalid")
        if not isinstance(self.status, AdaptationControlStatus):
            raise ValueError("adaptation receipt status is invalid")
        if self.before_revision > self.state.revision or self.before_revision < 0:
            raise ValueError("adaptation receipt revision is invalid")
        if self.status is AdaptationControlStatus.APPLIED:
            if self.state.revision != self.before_revision + 1:
                raise ValueError("applied adaptation control must advance revision")
        elif self.state.revision != self.before_revision:
            raise ValueError("unchanged adaptation control cannot advance revision")
        if any(
            isinstance(value, bool) or value < 0
            for value in (
                self.removed_learning_count,
                self.removed_snapshot_count,
                self.removed_prewarm_count,
            )
        ):
            raise ValueError("adaptation removal counts must be nonnegative")
        if self.operation is not AdaptationControlOperation.RESET and any(
            (self.removed_learning_count, self.removed_snapshot_count, self.removed_prewarm_count)
        ):
            raise ValueError("only reset may remove learned adaptation data")
        if not self.reason_codes or len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("adaptation control receipt needs unique reasons")
        _time(self.created_at)
        if not self.local_only:
            raise ValueError("adaptation control receipts must remain local")
        if self.contract_version != LIVE_ADAPTATION_CONTROL_VERSION:
            raise ValueError("unsupported live adaptation control version")


def selection_for(
    selections: tuple[WorkflowAdaptationSelection, ...], workflow_id: str,
) -> WorkflowAdaptationSelection | None:
    return next((item for item in selections if item.workflow_id == workflow_id), None)


def replace_selection(
    selections: tuple[WorkflowAdaptationSelection, ...],
    value: WorkflowAdaptationSelection,
) -> tuple[WorkflowAdaptationSelection, ...]:
    retained = tuple(item for item in selections if item.workflow_id != value.workflow_id)
    return tuple(sorted((*retained, value), key=lambda item: item.workflow_id))


def _selections(values: tuple[WorkflowAdaptationSelection, ...], name: str) -> None:
    if any(not isinstance(item, WorkflowAdaptationSelection) for item in values):
        raise ValueError(f"{name} adaptation selections are invalid")
    workflows = tuple(item.workflow_id for item in values)
    if len(set(workflows)) != len(workflows) or workflows != tuple(sorted(workflows)):
        raise ValueError(f"{name} adaptation selections must be unique and sorted")


def _text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("adaptation control timestamps must be timezone-aware")
