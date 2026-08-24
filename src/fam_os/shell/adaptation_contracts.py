"""Bounded Shell presentation contracts for owner-controlled adaptation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fam_os.adaptation import (
    AdaptationHealthSample,
    LiveAdaptationControlReceipt,
    LiveAdaptationControlState,
    LiveAdaptationDriftReport,
    LiveAdaptationSnapshot,
    ModelPrewarmReceipt,
)


SHELL_ADAPTATION_CONTRACT_VERSION = "fam.shell.adaptation/v1alpha1"
MAX_SHELL_ADAPTATION_PAGE = 100


class ShellAdaptationOperation(StrEnum):
    STATUS = "status"
    SNAPSHOTS = "snapshots"
    PREWARMS = "prewarms"
    HEALTH = "health"
    DRIFT = "drift"
    RECEIPTS = "receipts"


@dataclass(frozen=True, slots=True)
class ShellAdaptationQuery:
    request_id: str
    operation: ShellAdaptationOperation
    offset: int = 0
    limit: int = MAX_SHELL_ADAPTATION_PAGE
    contract_version: str = SHELL_ADAPTATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        if not isinstance(self.operation, ShellAdaptationOperation):
            raise ValueError("Shell adaptation operation is invalid")
        _page(self.offset, self.limit)
        if self.operation is ShellAdaptationOperation.STATUS and (
            self.offset != 0 or self.limit != 1
        ):
            raise ValueError("Shell adaptation status requires one result")
        if self.contract_version != SHELL_ADAPTATION_CONTRACT_VERSION:
            raise ValueError("unsupported Shell adaptation contract version")


@dataclass(frozen=True, slots=True)
class ShellAdaptationResponse:
    request_id: str
    operation: ShellAdaptationOperation
    offset: int
    total_count: int
    state: LiveAdaptationControlState | None = None
    snapshots: tuple[LiveAdaptationSnapshot, ...] = ()
    prewarms: tuple[ModelPrewarmReceipt, ...] = ()
    health: tuple[AdaptationHealthSample, ...] = ()
    drift_reports: tuple[LiveAdaptationDriftReport, ...] = ()
    control_receipts: tuple[LiveAdaptationControlReceipt, ...] = ()
    contract_version: str = SHELL_ADAPTATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        if not isinstance(self.operation, ShellAdaptationOperation):
            raise ValueError("Shell adaptation response operation is invalid")
        if isinstance(self.offset, bool) or self.offset < 0:
            raise ValueError("Shell adaptation response offset is invalid")
        if isinstance(self.total_count, bool) or self.total_count < 0:
            raise ValueError("Shell adaptation response count is invalid")
        collections = (
            self.snapshots, self.prewarms, self.health,
            self.drift_reports, self.control_receipts,
        )
        if any(len(values) > MAX_SHELL_ADAPTATION_PAGE for values in collections):
            raise ValueError("Shell adaptation response exceeds page limit")
        self._validate_shape(collections)
        if self.contract_version != SHELL_ADAPTATION_CONTRACT_VERSION:
            raise ValueError("unsupported Shell adaptation contract version")

    def _validate_shape(self, collections) -> None:
        if self.operation is ShellAdaptationOperation.STATUS:
            valid = self.state is not None and not any(collections)
            valid = valid and self.offset == 0 and self.total_count == 1
        else:
            index = {
                ShellAdaptationOperation.SNAPSHOTS: 0,
                ShellAdaptationOperation.PREWARMS: 1,
                ShellAdaptationOperation.HEALTH: 2,
                ShellAdaptationOperation.DRIFT: 3,
                ShellAdaptationOperation.RECEIPTS: 4,
            }[self.operation]
            valid = self.state is None
            valid = valid and all(not values for position, values in enumerate(collections) if position != index)
            valid = valid and self.total_count >= len(collections[index])
        if not valid:
            raise ValueError("Shell adaptation response shape does not match operation")


def _page(offset: int, limit: int) -> None:
    if isinstance(offset, bool) or offset < 0:
        raise ValueError("Shell adaptation offset is invalid")
    if isinstance(limit, bool) or not 1 <= limit <= MAX_SHELL_ADAPTATION_PAGE:
        raise ValueError("Shell adaptation limit is invalid")


def _text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
