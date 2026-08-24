import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from fam_os.expert_factory import (
    ConversionOutputType,
    ConversionStatus,
    TrainingTerminalStatus,
    build_evaluation_approval,
    build_evaluation_report,
    build_held_out_access_receipt,
    build_training_job,
    build_training_terminal_receipt,
    decide_comparison,
    build_conversion_approval,
    build_conversion_environment,
    build_conversion_receipt,
    FactoryCanaryStatus,
    build_canary_approval,
    build_canary_report,
    build_specialist_package_receipt,
    build_specialist_release_lineage,
    decide_canary_activation,
)
from fam_os.product.factory_training_approvals import ProductFactoryTrainingApprovals
from tests.unit.test_factory_evaluation import NOW, SIGNING_KEY, _measurement, _policy
from tests.unit.test_factory_training_approval import _issue_values, _repositories
from tests.unit.test_factory_training_backend import _environment


class FactoryEvaluationRepositoryTests(unittest.TestCase):
    def test_one_use_evaluation_is_encrypted_restart_safe_and_terminal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database, repositories, proposal_id, dataset = _repositories(root)
            training_approval, terminal = _completed_training(
                repositories, proposal_id, dataset,
            )
            held_out = next(
                item for item in repositories.sealed_datasets.blobs(dataset.dataset_id)
                if item.partition.value == "held_out"
            )
            policy = _policy()
            approval = build_evaluation_approval(
                approval_id="evaluation-approval-1", proposal_id=proposal_id,
                capability_id=training_approval.capability_id,
                training_receipt_id=terminal.receipt_id,
                adapter_sha256=terminal.adapter_sha256,
                adapter_config_sha256=terminal.adapter_config_sha256,
                sealed_dataset_id=dataset.dataset_id,
                sealed_dataset_sha256=dataset.manifest_sha256,
                held_out_blob_id=held_out.blob_id,
                held_out_blob_sha256=held_out.plaintext_sha256,
                incumbent_expert_id="qwen3-1.7b-base",
                incumbent_artifact_sha256=(
                    training_approval.base_model.files_manifest_sha256
                ),
                suite_sha256="5" * 64,
                evaluator_environment_sha256=terminal.environment_sha256,
                evaluator_script_sha256="6" * 64, policy=policy,
                one_use_evaluation_id="evaluation-1", issued_at=NOW,
                expires_at=NOW + timedelta(hours=1),
            )
            self.assertTrue(repositories.factory_evaluations.add_approval(approval))
            repositories.factory_evaluations.claim(
                approval.approval_id, approval.one_use_evaluation_id, 1, NOW,
            )
            with self.assertRaisesRegex(PermissionError, "already consumed"):
                repositories.factory_evaluations.claim(
                    approval.approval_id, approval.one_use_evaluation_id, 1, NOW,
                )
            repositories.factory_evaluations.mark_running(
                approval.one_use_evaluation_id, NOW,
            )
            access = build_held_out_access_receipt(
                receipt_id="held-out-access-1", approval_id=approval.approval_id,
                evaluation_id=approval.one_use_evaluation_id,
                dataset_id=dataset.dataset_id,
                held_out_blob_id=held_out.blob_id,
                held_out_blob_sha256=held_out.plaintext_sha256,
                evaluator_environment_sha256=approval.evaluator_environment_sha256,
                plaintext_bytes=1024, plaintext_discarded=True, accessed_at=NOW,
            )
            repositories.factory_evaluations.record_access(access)
            measurements = tuple(
                _measurement(index, baseline=False, candidate=True)
                for index in range(30)
            )
            report = build_evaluation_report(
                report_id="evaluation-report-1",
                approval_id=approval.approval_id,
                evaluation_id=approval.one_use_evaluation_id, policy=policy,
                evaluator_environment_sha256=approval.evaluator_environment_sha256,
                evaluator_script_sha256=approval.evaluator_script_sha256,
                held_out_access_receipt_sha256=access.receipt_sha256,
                network_denied=True,
                measurements=measurements,
                candidate_adapter_bytes=terminal.adapter_bytes,
                candidate_cold_start_microseconds=2_000_000,
                scheduler_compatible=True, started_at=NOW,
                finished_at=NOW + timedelta(minutes=1),
            )
            decision = decide_comparison(
                decision_id="evaluation-decision-1", approval=approval,
                report=report, decided_at=NOW + timedelta(minutes=1),
                signer_key_id="factory-evaluator-1", signing_key=SIGNING_KEY,
            )
            repositories.factory_evaluations.complete(
                measurements, report, decision,
            )
            conversion_environment = build_conversion_environment(
                environment_id="llama-cpp-conversion-v1",
                llama_cpp_revision="1" * 40,
                convert_hf_script_sha256="2" * 64,
                convert_lora_script_sha256="3" * 64,
                wheelhouse_manifest_sha256="4" * 64,
                python_executable_sha256="5" * 64,
                package_versions=(("torch", "2.11.0+cpu"),),
                ollama_version="0.13.5", observed_at=NOW,
            )
            repositories.factory_conversions.add_environment(conversion_environment)
            repeated_environment = replace(
                conversion_environment,
                observed_at=conversion_environment.observed_at + timedelta(seconds=1),
            )
            self.assertFalse(
                repositories.factory_conversions.add_environment(repeated_environment),
            )
            self.assertEqual(
                conversion_environment,
                repositories.factory_conversions.environment(
                    conversion_environment.manifest_sha256,
                ),
            )
            conversion_approval = build_conversion_approval(
                approval_id="conversion-approval-1",
                evaluation_id=decision.evaluation_id,
                comparison_decision_id=decision.decision_id,
                comparison_decision_sha256=decision.decision_sha256,
                adapter_sha256=approval.adapter_sha256,
                base_model_sha256=approval.incumbent_artifact_sha256,
                environment_sha256=conversion_environment.manifest_sha256,
                base_output_type=ConversionOutputType.BF16,
                adapter_output_type=ConversionOutputType.F16,
                runtime_model_ref="fam-code-specialist:canary",
                maximum_output_bytes=8_000_000_000,
                maximum_wall_seconds=3600,
                maximum_ram_bytes=32 * 1024**3,
                maximum_cpu_cores=12,
                one_use_conversion_id="conversion-1", issued_at=NOW,
                expires_at=NOW + timedelta(hours=1),
            )
            repositories.factory_conversions.add_approval(conversion_approval)
            conversion_receipt = build_conversion_receipt(
                receipt_id="conversion-receipt-1",
                approval_id=conversion_approval.approval_id,
                conversion_id=conversion_approval.one_use_conversion_id,
                comparison_decision_sha256=decision.decision_sha256,
                environment_sha256=conversion_environment.manifest_sha256,
                status=ConversionStatus.COMPLETED,
                reason_code="conversion.completed", base_gguf_sha256="6" * 64,
                base_gguf_bytes=4_000_000_000,
                adapter_gguf_sha256="7" * 64,
                adapter_gguf_bytes=30_000_000, modelfile_sha256="8" * 64,
                runtime_model_ref=conversion_approval.runtime_model_ref,
                network_denied=True, started_at=NOW, finished_at=NOW,
            )
            repositories.factory_conversions.complete(conversion_receipt, NOW)
            lineage = build_specialist_release_lineage(
                release_id="specialist-release-1",
                package_id="fam.specialist.code-1", package_version="1.0.0",
                expert_id="expert.specialist.code-1",
                training_capability_id=approval.capability_id,
                declared_capabilities=("code.generate.python",),
                required_verifier_ids=("python.deterministic-tests.v1",),
                conversion_receipt_id=conversion_receipt.receipt_id,
                conversion_receipt_sha256=conversion_receipt.receipt_sha256,
                conversion_environment_sha256=conversion_environment.manifest_sha256,
                comparison_decision_id=decision.decision_id,
                comparison_decision_sha256=decision.decision_sha256,
                training_receipt_id=terminal.receipt_id,
                sealed_dataset_id=dataset.dataset_id,
                sealed_dataset_sha256=dataset.manifest_sha256,
                base_model_id=training_approval.base_model.repository_id,
                base_model_revision=training_approval.base_model.revision,
                base_model_files_sha256=approval.incumbent_artifact_sha256,
                adapter_sha256=approval.adapter_sha256,
                base_gguf_sha256=conversion_receipt.base_gguf_sha256,
                adapter_gguf_sha256=conversion_receipt.adapter_gguf_sha256,
                modelfile_sha256=conversion_receipt.modelfile_sha256,
                tokenizer_sha256="9" * 64, chat_template_sha256="d" * 64,
                merge_policy="runtime_lora_adapter",
                base_output_type=conversion_approval.base_output_type,
                adapter_output_type=conversion_approval.adapter_output_type,
                runtime_model_ref=conversion_approval.runtime_model_ref,
                license_id=training_approval.base_model.license_id,
                estimated_resident_bytes=4_030_000_000,
                storage_bytes=4_030_000_000, max_context_tokens=8192,
                minimum_system_memory_bytes=8 * 1024**3,
                minimum_accelerator_memory_bytes=4 * 1024**3,
                accelerator_optional=True,
                supported_architectures=("x86_64",), created_at=NOW,
            )
            package_receipt = build_specialist_package_receipt(
                receipt_id="specialist-package-receipt-1",
                release_id=lineage.release_id, package_id=lineage.package_id,
                package_version=lineage.package_version,
                lineage_sha256=lineage.lineage_sha256,
                artifact_sha256="1" * 64, expert_manifest_sha256="2" * 64,
                runtime_binding_sha256="3" * 64,
                signature_sha256="4" * 64,
                signature_key_id="factory-package-key-1",
                validation_policy_id="factory-package-policy-1",
                compatibility_sha256="5" * 64,
                artifact_locator="packages/fam.specialist.code-1-1.0.0.tar",
                lifecycle_revision=1, installed_disabled=True,
                installed_at=NOW,
            )
            repositories.factory_releases.record_package(lineage, package_receipt)
            canary_approval = build_canary_approval(
                approval_id="canary-approval-1", release_id=lineage.release_id,
                package_receipt_sha256=package_receipt.receipt_sha256,
                package_id=lineage.package_id,
                package_version=lineage.package_version,
                expert_id=lineage.expert_id,
                runtime_model_ref=lineage.runtime_model_ref,
                capability_id=lineage.training_capability_id,
                verifier_id=lineage.required_verifier_ids[0],
                suite_sha256="6" * 64, case_count=2,
                maximum_output_tokens=512, maximum_wall_seconds=300,
                maximum_ram_bytes=16 * 1024**3,
                maximum_vram_bytes=15 * 1024**3,
                one_use_canary_id="canary-1", issued_at=NOW,
                expires_at=NOW + timedelta(hours=1),
            )
            repositories.factory_releases.add_canary_approval(canary_approval)
            repositories.factory_releases.claim_canary(
                canary_approval.approval_id,
                canary_approval.one_use_canary_id, 1, NOW,
            )
            canary_report = build_canary_report(
                report_id="canary-report-1",
                approval_id=canary_approval.approval_id,
                canary_id=canary_approval.one_use_canary_id,
                package_receipt_sha256=package_receipt.receipt_sha256,
                suite_sha256=canary_approval.suite_sha256,
                runtime_manifest_sha256="7" * 64,
                status=FactoryCanaryStatus.COMPLETED,
                reason_code="canary.completed", case_count=2,
                passed_case_count=2, verifier_failure_count=0,
                scheduler_selected_declared_capability=True,
                scheduler_excluded_unrelated_capabilities=True,
                outputs_discarded=True, peak_ram_bytes=4 * 1024**3,
                peak_vram_bytes=4 * 1024**3,
                started_at=NOW, finished_at=NOW,
            )
            activation = decide_canary_activation(
                decision_id="canary-activation-1", approval=canary_approval,
                report=canary_report, signer_key_id="factory-canary-key-1",
                signing_key=SIGNING_KEY, decided_at=NOW,
            )
            repositories.factory_releases.complete_canary(
                canary_report, activation,
            )
            database.close()

            database, repositories, _, _ = _repositories(root, seed=False)
            self.assertEqual(
                approval,
                repositories.factory_evaluations.approval(approval.approval_id),
            )
            self.assertEqual(
                access,
                repositories.factory_evaluations.access_receipt(
                    approval.one_use_evaluation_id,
                ),
            )
            self.assertEqual(
                measurements,
                repositories.factory_evaluations.measurements(
                    approval.one_use_evaluation_id,
                ),
            )
            self.assertEqual(
                report,
                repositories.factory_evaluations.report(
                    approval.one_use_evaluation_id,
                ),
            )
            self.assertEqual(
                decision,
                repositories.factory_evaluations.decision(
                    approval.one_use_evaluation_id,
                ),
            )
            self.assertEqual(
                conversion_receipt,
                repositories.factory_conversions.receipt("conversion-1"),
            )
            self.assertEqual(
                (conversion_environment,),
                repositories.factory_conversions.environments(),
            )
            self.assertEqual(
                (conversion_approval,),
                repositories.factory_conversions.approvals(),
            )
            self.assertEqual(
                (conversion_receipt,),
                repositories.factory_conversions.receipts(),
            )
            self.assertEqual(lineage, repositories.factory_releases.lineage(
                lineage.release_id,
            ))
            self.assertEqual(
                package_receipt,
                repositories.factory_releases.package_receipt(
                    package_receipt.receipt_id,
                ),
            )
            self.assertEqual(
                canary_report,
                repositories.factory_releases.canary_report("canary-1"),
            )
            self.assertEqual(
                activation,
                repositories.factory_releases.activation_decision("canary-1"),
            )
            self.assertEqual(
                (lineage,), repositories.factory_releases.lineages(),
            )
            self.assertEqual(
                (package_receipt,),
                repositories.factory_releases.package_receipts(),
            )
            self.assertEqual(
                (canary_approval,),
                repositories.factory_releases.canary_approvals(),
            )
            self.assertEqual(
                (canary_report,),
                repositories.factory_releases.canary_reports(),
            )
            self.assertEqual(
                (activation,),
                repositories.factory_releases.activation_decisions(),
            )
            database.close()


def _completed_training(repositories, proposal_id, dataset):
    environment = _environment()
    repositories.training_jobs.add_environment(environment)
    values = {
        **_issue_values(proposal_id, dataset),
        "environment_sha256": environment.manifest_sha256,
    }
    approval = ProductFactoryTrainingApprovals(
        repositories, now=lambda: NOW,
    ).issue(**values)
    blobs = repositories.sealed_datasets.blobs(dataset.dataset_id)
    train = next(item for item in blobs if item.partition.value == "train")
    validation = next(item for item in blobs if item.partition.value == "validation")
    consumption_id = f"training-consumption-{approval.approval_id}"
    job = build_training_job(
        job_id=approval.one_use_job_id, approval_id=approval.approval_id,
        approval_revision=1,
        approval_consumption_receipt_id=consumption_id,
        proposal_id=approval.proposal_id, capability_id=approval.capability_id,
        dataset_id=dataset.dataset_id,
        dataset_manifest_sha256=dataset.manifest_sha256,
        train_blob_sha256=train.plaintext_sha256,
        validation_blob_sha256=validation.plaintext_sha256,
        base_model_files_sha256=approval.base_model.files_manifest_sha256,
        environment_sha256=environment.manifest_sha256, admitted_at=NOW,
    )
    repositories.training_jobs.admit(job, NOW)
    repositories.training_jobs.mark_running(job.job_id, NOW)
    terminal = build_training_terminal_receipt(
        receipt_id="training-terminal-evaluation", job_id=job.job_id,
        approval_id=approval.approval_id,
        environment_sha256=environment.manifest_sha256,
        status=TrainingTerminalStatus.COMPLETED,
        reason_code="training.completed", adapter_sha256="a" * 64,
        adapter_config_sha256="b" * 64, adapter_bytes=30_000_000,
        metrics_sha256="c" * 64, started_at=NOW, finished_at=NOW,
        exit_code=0, network_denied=True, held_out_absent=True,
        base_weights_frozen=True, unexpected_trainable_parameters=(),
        peak_ram_bytes=1024, peak_vram_bytes=1024,
        maximum_temperature_celsius=50, energy_joules=10,
    )
    repositories.training_jobs.record_terminal(terminal)
    return approval, terminal


if __name__ == "__main__":
    unittest.main()
