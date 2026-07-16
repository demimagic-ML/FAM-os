"""Ports used by Core's application-action safety envelope."""

from typing import Protocol

from fam_os.applications import (
    ActionConfirmation, ActionProposal, ActionResult, CapabilityRegistryEntry,
    ConditionEvidence, ConditionRequirement,
)


class ApplicationActionProvider(Protocol):
    def capability(
        self, instance_id: str, capability_id: str,
    ) -> CapabilityRegistryEntry | None: ...

    def execute_action(
        self, proposal: ActionProposal, confirmation: ActionConfirmation,
    ) -> ActionResult: ...


class ApplicationConditionVerifier(Protocol):
    def verify(
        self, requirement: ConditionRequirement, proposal: ActionProposal,
        provider_result: ActionResult | None,
    ) -> ConditionEvidence: ...


class ActionExecutionReplayRegistry(Protocol):
    def reserve(self, confirmation_id: str) -> bool: ...
