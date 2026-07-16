"""Activation-bound verifier adapter for application action conditions."""

from dataclasses import dataclass
from typing import Protocol

from fam_os.applications import ActionProposal, ActionResult, ConditionEvidence, ConditionRequirement
from fam_os.verification.trust import VerifierActivationDecision


class ConditionVerifierProvider(Protocol):
    def verify(
        self,
        requirement: ConditionRequirement,
        proposal: ActionProposal,
        provider_result: ActionResult | None,
    ) -> ConditionEvidence: ...


@dataclass(frozen=True, slots=True)
class ActivatedApplicationConditionVerifier:
    activation: VerifierActivationDecision
    provider: ConditionVerifierProvider

    def verify(self, requirement, proposal, provider_result=None) -> ConditionEvidence:
        if not self.activation.allowed or self.activation.verifier_id != requirement.verifier_id:
            return _failed(requirement, "Condition verifier is not trusted and activated.")
        evidence = self.provider.verify(requirement, proposal, provider_result)
        if evidence.condition_id != requirement.condition_id or evidence.verifier_id != requirement.verifier_id:
            return _failed(requirement, "Condition verifier returned mismatched authority.")
        return evidence


def _failed(requirement, details) -> ConditionEvidence:
    return ConditionEvidence(requirement.condition_id, requirement.verifier_id, False, details)
