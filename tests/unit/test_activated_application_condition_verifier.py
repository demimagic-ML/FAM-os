import unittest
from dataclasses import replace

from fam_os.applications import ConditionEvidence, ConditionRequirement
from fam_os.verification import ActivatedApplicationConditionVerifier, VerifierActivationDecision


class Provider:
    def verify(self, requirement, proposal, provider_result):
        return ConditionEvidence(requirement.condition_id, requirement.verifier_id, True, "passed")


class ActivatedApplicationConditionVerifierTests(unittest.TestCase):
    def setUp(self):
        self.requirement = ConditionRequirement("document.hash", "verifier.app-state", "hash matches")
        self.activation = VerifierActivationDecision(
            True, "accepted", "verifier.app-state", "package.app-state", "1.0.0",
            "policy", "a" * 64,
        )

    def test_exact_activated_verifier_can_emit_passing_condition(self):
        evidence = ActivatedApplicationConditionVerifier(self.activation, Provider()).verify(
            self.requirement, None, None
        )
        self.assertTrue(evidence.passed)

    def test_denied_or_wrong_verifier_fails_condition_closed(self):
        for activation in (
            replace(self.activation, allowed=False, reason_code="denied", verified_artifact_digest=None),
            replace(self.activation, verifier_id="verifier.other"),
        ):
            with self.subTest(reason=activation.reason_code):
                evidence = ActivatedApplicationConditionVerifier(activation, Provider()).verify(
                    self.requirement, None, None
                )
                self.assertFalse(evidence.passed)


if __name__ == "__main__":
    unittest.main()
