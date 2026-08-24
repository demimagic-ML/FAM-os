import unittest
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.expert_factory import (
    EvaluationCaseKind,
    build_evaluation_approval,
    build_evaluation_policy,
    build_evaluation_report,
    build_held_out_access_receipt,
    build_paired_measurement,
    decide_comparison,
)


NOW = datetime(2026, 7, 18, tzinfo=UTC)
GIB = 1024**3
SIGNING_KEY = Ed25519PrivateKey.from_private_bytes(b"e" * 32)


class FactoryEvaluationContractTests(unittest.TestCase):
    def test_confident_improvement_and_all_hard_gates_are_required(self):
        policy = _policy()
        approval = _approval(policy)
        measurements = tuple(
            _measurement(index, baseline=False, candidate=True)
            for index in range(30)
        ) + (
            _measurement(100, kind=EvaluationCaseKind.SAFETY),
            _measurement(101, kind=EvaluationCaseKind.POLICY),
            _measurement(102, kind=EvaluationCaseKind.UNRELATED),
        )
        report = build_evaluation_report(
            report_id="evaluation-report-1", approval_id=approval.approval_id,
            evaluation_id=approval.one_use_evaluation_id, policy=policy,
            evaluator_environment_sha256=approval.evaluator_environment_sha256,
            evaluator_script_sha256=approval.evaluator_script_sha256,
            held_out_access_receipt_sha256="9" * 64, network_denied=True,
            measurements=measurements, candidate_adapter_bytes=30_000_000,
            candidate_cold_start_microseconds=2_000_000,
            scheduler_compatible=True, started_at=NOW,
            finished_at=NOW + timedelta(minutes=1),
        )
        decision = decide_comparison(
            decision_id="evaluation-decision-1", approval=approval,
            report=report, decided_at=NOW + timedelta(minutes=1),
            signer_key_id="factory-evaluator-1", signing_key=SIGNING_KEY,
        )
        self.assertTrue(decision.promotable)
        self.assertGreater(
            report.candidate_quality_lower_ppm,
            report.baseline_quality_upper_ppm,
        )

    def test_small_unimproved_unsafe_candidate_is_not_promotable(self):
        policy = _policy()
        approval = _approval(policy)
        measurements = tuple(
            _measurement(index, baseline=True, candidate=True)
            for index in range(10)
        ) + (
            _measurement(
                100, kind=EvaluationCaseKind.SAFETY,
                baseline=True, candidate=False,
            ),
        )
        report = build_evaluation_report(
            report_id="evaluation-report-2", approval_id=approval.approval_id,
            evaluation_id=approval.one_use_evaluation_id, policy=policy,
            evaluator_environment_sha256=approval.evaluator_environment_sha256,
            evaluator_script_sha256=approval.evaluator_script_sha256,
            held_out_access_receipt_sha256="9" * 64, network_denied=True,
            measurements=measurements, candidate_adapter_bytes=30_000_000,
            candidate_cold_start_microseconds=2_000_000,
            scheduler_compatible=False, started_at=NOW,
            finished_at=NOW + timedelta(minutes=1),
        )
        decision = decide_comparison(
            decision_id="evaluation-decision-2", approval=approval,
            report=report, decided_at=NOW + timedelta(minutes=1),
            signer_key_id="factory-evaluator-1", signing_key=SIGNING_KEY,
        )
        self.assertFalse(decision.promotable)
        self.assertIn("quality.sample_count_insufficient", decision.reason_codes)
        self.assertIn("quality.confident_improvement_not_met", decision.reason_codes)
        self.assertIn("safety.failed", decision.reason_codes)
        self.assertIn("scheduler.incompatible", decision.reason_codes)

    def test_held_out_access_receipt_requires_plaintext_disposal(self):
        receipt = build_held_out_access_receipt(
            receipt_id="held-out-access-1", approval_id="evaluation-approval-1",
            evaluation_id="evaluation-1", dataset_id="dataset-1",
            held_out_blob_id="blob-held-out-1", held_out_blob_sha256="a" * 64,
            evaluator_environment_sha256="b" * 64, plaintext_bytes=1024,
            plaintext_discarded=True, accessed_at=NOW,
        )
        self.assertTrue(receipt.plaintext_discarded)


def _policy():
    return build_evaluation_policy(
        policy_id="code-specialist-evaluation-v1", capability_id="intent.code",
        minimum_quality_cases=30, minimum_quality_ppm=800_000,
        minimum_improvement_ppm=100_000, confidence_z_ppm=1_960_000,
        maximum_unrelated_regression_ppm=0,
        maximum_p95_latency_microseconds=5_000_000,
        maximum_latency_regression_ppm=200_000,
        maximum_peak_ram_bytes=8 * GIB, maximum_peak_vram_bytes=8 * GIB,
        maximum_energy_joules=10_000, maximum_resource_regression_ppm=200_000,
        maximum_adapter_bytes=100_000_000,
        maximum_cold_start_microseconds=10_000_000,
        require_scheduler_compatibility=True,
    )


def _approval(policy):
    return build_evaluation_approval(
        approval_id="evaluation-approval-1", proposal_id="proposal-1",
        capability_id="intent.code", training_receipt_id="training-terminal-1",
        adapter_sha256="1" * 64, adapter_config_sha256="2" * 64,
        sealed_dataset_id="dataset-1", sealed_dataset_sha256="3" * 64,
        held_out_blob_id="blob-held-out-1", held_out_blob_sha256="4" * 64,
        incumbent_expert_id="qwen3-1.7b-base",
        incumbent_artifact_sha256="5" * 64, suite_sha256="6" * 64,
        evaluator_environment_sha256="7" * 64,
        evaluator_script_sha256="8" * 64, policy=policy,
        one_use_evaluation_id="evaluation-1", issued_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )


def _measurement(
    index, *, kind=EvaluationCaseKind.QUALITY,
    baseline=True, candidate=True,
):
    return build_paired_measurement(
        measurement_id=f"measurement-{index}", evaluation_id="evaluation-1",
        case_id=f"case-{index}", kind=kind,
        requirement_id=f"acceptance.{kind.value}",
        input_sha256=f"{index % 10}" * 64,
        expected_sha256=f"{(index + 1) % 10}" * 64,
        baseline_output_sha256="a" * 64, candidate_output_sha256="b" * 64,
        baseline_passed=baseline, candidate_passed=candidate,
        baseline_latency_microseconds=1_000_000,
        candidate_latency_microseconds=1_100_000,
        baseline_peak_ram_bytes=2 * GIB, candidate_peak_ram_bytes=2 * GIB,
        baseline_peak_vram_bytes=3 * GIB, candidate_peak_vram_bytes=3 * GIB,
        baseline_energy_millijoules=1_000,
        candidate_energy_millijoules=1_100, measured_at=NOW,
    )


if __name__ == "__main__":
    unittest.main()
