import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.expert_factory import (
    FactoryCanaryStatus,
    build_canary_approval,
    build_canary_report,
    decide_canary_activation,
)


NOW = datetime(2026, 7, 18, tzinfo=UTC)


class FactoryCanaryContractTests(unittest.TestCase):
    def test_complete_verified_scoped_canary_signs_activation(self) -> None:
        approval = _approval()
        report = _report(approval)
        decision = decide_canary_activation(
            decision_id="canary-activation-1", approval=approval, report=report,
            signer_key_id="factory-canary-key-1",
            signing_key=Ed25519PrivateKey.from_private_bytes(b"c" * 32),
            decided_at=NOW,
        )
        self.assertTrue(decision.activate)
        self.assertEqual((), decision.reason_codes)
        with self.assertRaisesRegex(ValueError, "signature"):
            replace(decision, signature_base64="A" * 88)

    def test_verifier_or_scheduler_failure_signs_denial(self) -> None:
        approval = _approval()
        report = _report(
            approval, passed_case_count=1, verifier_failure_count=1,
            scheduler_selected_declared_capability=False,
        )
        decision = decide_canary_activation(
            decision_id="canary-activation-denied", approval=approval,
            report=report, signer_key_id="factory-canary-key-1",
            signing_key=Ed25519PrivateKey.from_private_bytes(b"c" * 32),
            decided_at=NOW,
        )
        self.assertFalse(decision.activate)
        self.assertIn("canary.verifier_failed", decision.reason_codes)
        self.assertIn("canary.scheduler_selection_failed", decision.reason_codes)


def _approval():
    return build_canary_approval(
        approval_id="canary-approval-1", release_id="specialist-release-1",
        package_receipt_sha256="1" * 64,
        package_id="fam.specialist.code-1", package_version="1.0.0",
        expert_id="expert.specialist.code-1",
        runtime_model_ref="fam-code-specialist:canary",
        capability_id="intent.code",
        verifier_id="python.deterministic-tests.v1",
        suite_sha256="2" * 64, case_count=2, maximum_output_tokens=512,
        maximum_wall_seconds=300, maximum_ram_bytes=16 * 1024**3,
        maximum_vram_bytes=15 * 1024**3,
        one_use_canary_id="canary-1", issued_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )


def _report(approval, **changes):
    values = {
        "report_id": "canary-report-1", "approval_id": approval.approval_id,
        "canary_id": approval.one_use_canary_id,
        "package_receipt_sha256": approval.package_receipt_sha256,
        "suite_sha256": approval.suite_sha256,
        "runtime_manifest_sha256": "3" * 64,
        "status": FactoryCanaryStatus.COMPLETED,
        "reason_code": "canary.completed", "case_count": 2,
        "passed_case_count": 2, "verifier_failure_count": 0,
        "scheduler_selected_declared_capability": True,
        "scheduler_excluded_unrelated_capabilities": True,
        "outputs_discarded": True, "peak_ram_bytes": 4 * 1024**3,
        "peak_vram_bytes": 4 * 1024**3,
        "started_at": NOW, "finished_at": NOW + timedelta(seconds=10),
    }
    values.update(changes)
    return build_canary_report(**values)


if __name__ == "__main__":
    unittest.main()
