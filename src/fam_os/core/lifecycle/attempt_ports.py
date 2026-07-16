"""Trusted policy and replay ports for bounded attempts."""

from typing import Protocol

from fam_os.core.lifecycle.attempt_contracts import AttemptBudgetPolicy


class AttemptPolicyRegistry(Protocol):
    def get(self, plan_id: str) -> AttemptBudgetPolicy | None: ...


class AttemptReplayRegistry(Protocol):
    def reserve(self, attempt_ids: tuple[str, ...]) -> bool: ...
