"""Deadline policy and replay ports for lifecycle controls."""

from typing import Protocol

from fam_os.core.lifecycle.control_contracts import PlanDeadlinePolicy


class DeadlinePolicyRegistry(Protocol):
    def get(self, plan_id: str) -> PlanDeadlinePolicy | None: ...


class ControlReplayRegistry(Protocol):
    def reserve(self, control_id: str) -> bool: ...
