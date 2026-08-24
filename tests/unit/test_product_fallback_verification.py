import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from fam_os.applications import (
    ConditionEvidence, ConditionRequirement, ObservationResult, ObservationStatus,
)
from fam_os.product.composition.application_conditions import (
    LiveApplicationConditionVerifier,
)


NOW = datetime(2026, 7, 17, tzinfo=timezone.utc)


class ProductFallbackVerificationTests(unittest.TestCase):
    def test_accessibility_poststate_requires_independent_tree_match(self):
        requirement = ConditionRequirement(
            "accessibility.action.poststate", "accessibility.action.poststate",
            "Poststate must be independently visible.",
        )
        result = _provider_result(requirement, after_fingerprint="a" * 64)
        matching = _accessibility_observation("a" * 64)
        evidence = LiveApplicationConditionVerifier(Provider(matching)).verify(
            requirement, _proposal("atspi-instance", "process:100"), result,
        )
        self.assertTrue(evidence.passed)
        mismatched = LiveApplicationConditionVerifier(
            Provider(_accessibility_observation("b" * 64))
        ).verify(requirement, _proposal("atspi-instance", "process:100"), result)
        self.assertFalse(mismatched.passed)

    def test_screen_postframe_requires_fresh_exact_scene_and_provider_evidence(self):
        requirement = ConditionRequirement(
            "screen.input.postframe", "screen.input.postframe",
            "Postframe must be independently visible.",
        )
        result = _provider_result(requirement, after_scene_id="scene-after")
        evidence = LiveApplicationConditionVerifier(
            Provider(_screen_observation("scene-after"))
        ).verify(requirement, _proposal("screen-instance", "window:0x2a"), result)
        self.assertTrue(evidence.passed)
        failed_provider = SimpleNamespace(
            output=result.output,
            postcondition_evidence=(ConditionEvidence(
                requirement.condition_id, requirement.verifier_id, False, "failed",
            ),),
        )
        rejected = LiveApplicationConditionVerifier(
            Provider(_screen_observation("scene-after"))
        ).verify(
            requirement, _proposal("screen-instance", "window:0x2a"), failed_provider,
        )
        self.assertFalse(rejected.passed)


class Provider:
    def __init__(self, observation):
        self.observation = observation
        self.requests = []

    def observe(self, request):
        self.requests.append(request)
        return self.observation


def _proposal(instance_id: str, resource_uri: str):
    request = SimpleNamespace(
        instance_id=instance_id, permission_grant_id="permission-1",
        resource_uri=resource_uri,
    )
    return SimpleNamespace(request=request)


def _provider_result(requirement, **output):
    return SimpleNamespace(
        output=output,
        postcondition_evidence=(ConditionEvidence(
            requirement.condition_id, requirement.verifier_id, True, "provider passed",
        ),),
    )


def _accessibility_observation(fingerprint: str):
    return ObservationResult(
        "observed-atspi", ObservationStatus.OBSERVED, NOW,
        {"nodes": [{"reference": {"fingerprint": fingerprint}}]},
        "process:100", "tree-revision",
    )


def _screen_observation(scene: str):
    return ObservationResult(
        "observed-screen", ObservationStatus.OBSERVED, NOW,
        {"frame": {"scene_id": scene}}, "window:0x2a", scene,
    )


if __name__ == "__main__":
    unittest.main()
