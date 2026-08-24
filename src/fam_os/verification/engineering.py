"""Trusted verifier over signed-recipe engineering tool receipts."""

from dataclasses import dataclass

from fam_os.core.engineering.execution import EngineeringToolReceipt, ToolQualificationStatus
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog


@dataclass(frozen=True, slots=True)
class EngineeringVerificationVerdict:
    passed: bool
    verifier_ids: tuple[str, ...]
    reason: str


class SignedEngineeringReceiptVerifier:
    def __init__(self, recipes: SignedToolRecipeCatalog) -> None:
        self._recipes = recipes

    def verify(self, receipt: EngineeringToolReceipt, recipe_version: str) -> EngineeringVerificationVerdict:
        recipe = self._recipes.get(receipt.recipe_id, recipe_version)
        if receipt.recipe_payload_sha256 != recipe.payload_sha256:
            return EngineeringVerificationVerdict(False, recipe.verifier_ids, "recipe digest differs from trusted signed recipe")
        if receipt.network_destinations and recipe.network_mode.value == "denied":
            return EngineeringVerificationVerdict(False, recipe.verifier_ids, "network-denied recipe observed a destination")
        required = {"bubblewrap-unshare-all", "cgroup-v2-systemd", "bounded-rlimits"}
        if not required.issubset(receipt.isolation_evidence_ids):
            return EngineeringVerificationVerdict(False, recipe.verifier_ids, "required containment evidence is absent")
        if receipt.status is not ToolQualificationStatus.PASSED:
            return EngineeringVerificationVerdict(False, recipe.verifier_ids, "tool recipe did not pass")
        return EngineeringVerificationVerdict(True, recipe.verifier_ids, "signed recipe and containment evidence passed")
