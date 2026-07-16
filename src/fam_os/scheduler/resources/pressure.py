"""Current provider-neutral resource-pressure readings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


def _require_fraction(name: str, value: float | None) -> None:
    if value is not None and not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between zero and one")


@dataclass(frozen=True, slots=True)
class PressureReading:
    """A normalized utilization and/or stall observation for one resource ID."""

    resource_id: str
    observed_at: datetime
    utilization_fraction: float | None = None
    stall_fraction: float | None = None

    def __post_init__(self) -> None:
        if not self.resource_id.strip():
            raise ValueError("pressure resource_id must not be empty")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.utilization_fraction is None and self.stall_fraction is None:
            raise ValueError("pressure reading requires utilization or stall data")
        _require_fraction("utilization_fraction", self.utilization_fraction)
        _require_fraction("stall_fraction", self.stall_fraction)
