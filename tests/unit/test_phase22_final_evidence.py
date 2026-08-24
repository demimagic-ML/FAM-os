from __future__ import annotations

import unittest

from tools.phase22_release_exit.final_evidence import _phase_checks


class Phase22FinalEvidenceTests(unittest.TestCase):
    def test_complete_physical_release_lifecycle_passes_all_checks(self) -> None:
        checks = _phase_checks(_training(), _release())

        self.assertTrue(all(checks.values()))

    def test_missing_rollback_removal_fails_the_exit(self) -> None:
        release = _release()
        release["rollback"]["runtime_model_removed"] = False

        checks = _phase_checks(_training(), release)

        self.assertFalse(checks["rollback_removed_runtime"])
        self.assertFalse(all(checks.values()))


def _training():
    return {
        "passed": True,
        "evaluation": {
            "promotable": True,
            "held_out_plaintext_discarded": True,
        },
        "training": {
            "base_weights_frozen": True,
            "held_out_absent": True,
            "network_denied": True,
        },
    }


def _release():
    return {
        "activation": {"activate": True},
        "audit_retained": True,
        "canary": {
            "case_count": 1,
            "outputs_discarded": True,
            "passed_case_count": 1,
            "status": "completed",
            "verifier_failure_count": 0,
        },
        "conversion": {"network_denied": True, "status": "completed"},
        "package": {"installed_disabled": True},
        "passed": True,
        "reactivated_lifecycle_revision": 3,
        "retirement": {
            "artifact_removed": True,
            "runtime_model_removed": True,
        },
        "rollback": {"runtime_model_removed": True},
    }


if __name__ == "__main__":
    unittest.main()
