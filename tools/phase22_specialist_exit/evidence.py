"""Content-free evidence for one real specialist learning-curve checkpoint."""

from __future__ import annotations

from collections import Counter
from typing import Any

from tools.phase22_specialist_exit.dataset import PreparedSpecialistDataset
from tools.phase22_specialist_exit.evaluation import CompletedSpecialistEvaluation
from tools.phase22_specialist_exit.suite import SealedEvaluationSuite
from tools.phase22_specialist_exit.training import CompletedSpecialistTraining


def build_specialist_evidence(
    *, run_id: str, suite: SealedEvaluationSuite,
    prepared: PreparedSpecialistDataset,
    training: CompletedSpecialistTraining,
    evaluation: CompletedSpecialistEvaluation,
) -> dict[str, Any]:
    partitions = {
        item.partition.value: _partition_evidence(item)
        for item in prepared.dataset.partitions
    }
    verifiers = Counter(item.verifier_id for item in prepared.fixture_receipts)
    report = evaluation.report
    terminal = training.terminal
    decision = evaluation.decision
    return {
        "contract_version": "fam.factory.specialist-checkpoint/v1alpha1",
        "run_id": run_id,
        "sealed_suite": {
            "case_count": suite.case_count,
            "sha256": suite.sha256,
            "sealed_before_dataset_capture": True,
        },
        "failure_discovery": {
            "proposal_id": prepared.proposal.proposal_id,
            "capability_id": prepared.proposal.capability_id,
            "failed_requirement_id": prepared.proposal.failed_requirement_id,
            "observation_count": prepared.proposal.observation_count,
        },
        "dataset": {
            "sample_plan_id": prepared.sample_plan_id,
            "dataset_id": prepared.dataset.dataset_id,
            "manifest_sha256": prepared.dataset.manifest_sha256,
            "split_policy_id": prepared.dataset.split_policy_id,
            "partitions": partitions,
            "license_ids": list(prepared.dataset.license_ids),
            "sensitivities": list(prepared.dataset.sensitivities),
            "leakage_report_id": prepared.leakage.report_id,
            "leakage_report_sha256": prepared.leakage.report_sha256,
            "leakage_passed": prepared.leakage.passed,
            "fixture_verification_count": len(prepared.fixture_receipts),
            "fixture_verification_passed": all(
                item.passed for item in prepared.fixture_receipts
            ),
            "fixture_verifiers": dict(sorted(verifiers.items())),
        },
        "training": {
            "environment_sha256": training.environment.manifest_sha256,
            "approval_id": training.approval.approval_id,
            "approved_dataset_sha256": (
                training.approval.sealed_dataset_sha256
            ),
            "recipe_id": training.approval.recipe.recipe_id,
            "resource_budget_id": training.approval.resources.budget_id,
            "job_id": terminal.job_id,
            "receipt_id": terminal.receipt_id,
            "receipt_sha256": terminal.receipt_sha256,
            "status": terminal.status.value,
            "adapter_sha256": terminal.adapter_sha256,
            "adapter_config_sha256": terminal.adapter_config_sha256,
            "adapter_bytes": terminal.adapter_bytes,
            "base_weights_frozen": terminal.base_weights_frozen,
            "network_denied": terminal.network_denied,
            "held_out_absent": terminal.held_out_absent,
            "peak_ram_bytes": terminal.peak_ram_bytes,
            "peak_vram_bytes": terminal.peak_vram_bytes,
            "maximum_temperature_celsius": terminal.maximum_temperature_celsius,
            "energy_joules": terminal.energy_joules,
        },
        "evaluation": {
            "environment_sha256": evaluation.environment.manifest_sha256,
            "approval_id": evaluation.approval.approval_id,
            "approval_sha256": evaluation.approval.approval_sha256,
            "evaluation_id": decision.evaluation_id,
            "measurement_count": len(evaluation.measurements),
            "report_sha256": report.report_sha256,
            "decision_sha256": decision.decision_sha256,
            "signature_base64": decision.signature_base64,
            "signer_key_id": decision.signer_key_id,
            "promotable": decision.promotable,
            "reason_codes": list(decision.reason_codes),
            "quality_case_count": report.quality_case_count,
            "baseline_quality_ppm": report.baseline_quality_ppm,
            "candidate_quality_ppm": report.candidate_quality_ppm,
            "baseline_quality_upper_ppm": report.baseline_quality_upper_ppm,
            "candidate_quality_lower_ppm": report.candidate_quality_lower_ppm,
            "candidate_safety_failures": report.candidate_safety_failures,
            "candidate_policy_failures": report.candidate_policy_failures,
            "baseline_unrelated_quality_ppm": report.baseline_unrelated_quality_ppm,
            "candidate_unrelated_quality_ppm": report.candidate_unrelated_quality_ppm,
            "baseline_p95_latency_microseconds": (
                report.baseline_p95_latency_microseconds
            ),
            "candidate_p95_latency_microseconds": (
                report.candidate_p95_latency_microseconds
            ),
            "candidate_peak_ram_bytes": report.candidate_peak_ram_bytes,
            "candidate_peak_vram_bytes": report.candidate_peak_vram_bytes,
            "candidate_energy_joules": report.candidate_energy_joules,
            "candidate_adapter_bytes": report.candidate_adapter_bytes,
            "scheduler_compatible": report.scheduler_compatible,
            "network_denied": report.network_denied,
            "held_out_plaintext_discarded": (
                evaluation.access_receipt.plaintext_discarded
            ),
        },
        "passed": (
            prepared.leakage.passed
            and terminal.status.value == "completed"
            and report.network_denied
            and evaluation.access_receipt.plaintext_discarded
            and decision.promotable
        ),
    }


def _partition_evidence(partition: Any) -> dict[str, object]:
    return {
        "blob_id": partition.blob_id,
        "ordered_records_sha256": partition.ordered_records_sha256,
        "content_bytes": partition.content_bytes,
        "record_count": partition.record_count,
    }
