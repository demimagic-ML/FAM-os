import unittest
import tempfile
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.expert_factory import (
    TrainingTerminalStatus,
    build_training_environment,
    build_training_job,
    build_training_terminal_receipt,
)
from fam_os.product.factory_training_approvals import ProductFactoryTrainingApprovals
from tests.unit.test_factory_training_approval import _issue_values, _repositories


NOW = datetime(2026, 7, 17, 22, tzinfo=UTC)
GIB = 1024**3


class FactoryTrainingBackendContractTests(unittest.TestCase):
    def test_environment_job_and_terminal_receipt_are_digest_bound(self):
        environment = _environment()
        job = build_training_job(
            job_id="training-job-1", approval_id="training-approval-1",
            approval_revision=1,
            approval_consumption_receipt_id="training-consumption-1",
            proposal_id="proposal-1", capability_id="intent.code",
            dataset_id="sealed-dataset-1", dataset_manifest_sha256="a" * 64,
            train_blob_sha256="b" * 64, validation_blob_sha256="c" * 64,
            base_model_files_sha256="d" * 64,
            environment_sha256=environment.manifest_sha256, admitted_at=NOW,
        )
        receipt = build_training_terminal_receipt(
            receipt_id="training-terminal-1", job_id=job.job_id,
            approval_id=job.approval_id,
            environment_sha256=environment.manifest_sha256,
            status=TrainingTerminalStatus.COMPLETED,
            reason_code="training.completed", adapter_sha256="e" * 64,
            adapter_config_sha256="f" * 64, adapter_bytes=1024,
            metrics_sha256="1" * 64, started_at=NOW,
            finished_at=NOW + timedelta(minutes=1), exit_code=0,
            network_denied=True, held_out_absent=True,
            base_weights_frozen=True, unexpected_trainable_parameters=(),
            peak_ram_bytes=2 * GIB, peak_vram_bytes=GIB,
            maximum_temperature_celsius=61, energy_joules=500,
        )

        with self.assertRaisesRegex(ValueError, "manifest digest"):
            replace(environment, device_name="different GPU")
        with self.assertRaisesRegex(ValueError, "exclude held-out"):
            replace(job, held_out_excluded=False)
        with self.assertRaisesRegex(ValueError, "receipt digest"):
            replace(receipt, peak_vram_bytes=2 * GIB)

    def test_completed_training_requires_isolation_and_only_adapter_parameters(self):
        receipt = build_training_terminal_receipt(
            receipt_id="training-terminal-1", job_id="training-job-1",
            approval_id="training-approval-1",
            environment_sha256=_environment().manifest_sha256,
            status=TrainingTerminalStatus.COMPLETED,
            reason_code="training.completed", adapter_sha256="e" * 64,
            adapter_config_sha256="f" * 64, adapter_bytes=1024,
            metrics_sha256="1" * 64, started_at=NOW, finished_at=NOW,
            exit_code=0, network_denied=True, held_out_absent=True,
            base_weights_frozen=True, unexpected_trainable_parameters=(),
            peak_ram_bytes=1, peak_vram_bytes=1,
            maximum_temperature_celsius=50, energy_joules=1,
        )
        with self.assertRaisesRegex(ValueError, "isolation"):
            replace(receipt, network_denied=False)
        with self.assertRaisesRegex(ValueError, "unapproved parameters"):
            replace(receipt, unexpected_trainable_parameters=("model.weight",))

        failed = build_training_terminal_receipt(
            receipt_id="training-terminal-failed", job_id="training-job-failed",
            approval_id="training-approval-failed",
            environment_sha256=_environment().manifest_sha256,
            status=TrainingTerminalStatus.FAILED,
            reason_code="training.environment_unavailable",
            adapter_sha256=None, adapter_config_sha256=None, adapter_bytes=0,
            metrics_sha256="2" * 64, started_at=NOW, finished_at=NOW,
            exit_code=1, network_denied=False, held_out_absent=False,
            base_weights_frozen=False, unexpected_trainable_parameters=(),
            peak_ram_bytes=0, peak_vram_bytes=0,
            maximum_temperature_celsius=0, energy_joules=0,
        )
        self.assertFalse(failed.network_denied)

    def test_job_and_terminal_evidence_are_restart_safe_and_one_use_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database, repositories, proposal_id, dataset = _repositories(root)
            environment = _environment()
            self.assertTrue(repositories.training_jobs.add_environment(environment))
            approval_values = {
                **_issue_values(proposal_id, dataset),
                "environment_sha256": environment.manifest_sha256,
            }
            approval = ProductFactoryTrainingApprovals(
                repositories, now=lambda: NOW,
            ).issue(**approval_values)
            consumption_id = f"training-consumption-{approval.approval_id}"
            blobs = repositories.sealed_datasets.blobs(dataset.dataset_id)
            job = build_training_job(
                job_id=approval.one_use_job_id, approval_id=approval.approval_id,
                approval_revision=1,
                approval_consumption_receipt_id=consumption_id,
                proposal_id=approval.proposal_id,
                capability_id=approval.capability_id, dataset_id=dataset.dataset_id,
                dataset_manifest_sha256=dataset.manifest_sha256,
                train_blob_sha256=blobs[0].plaintext_sha256,
                validation_blob_sha256=blobs[1].plaintext_sha256,
                base_model_files_sha256=approval.base_model.files_manifest_sha256,
                environment_sha256=environment.manifest_sha256, admitted_at=NOW,
            )
            consumption = repositories.training_jobs.admit(job, NOW)
            self.assertEqual(consumption_id, consumption.receipt_id)
            repositories.training_jobs.mark_running(job.job_id, NOW)
            receipt = build_training_terminal_receipt(
                receipt_id="training-terminal-restart", job_id=job.job_id,
                approval_id=approval.approval_id,
                environment_sha256=environment.manifest_sha256,
                status=TrainingTerminalStatus.FAILED,
                reason_code="training.worker_failed", adapter_sha256=None,
                adapter_config_sha256=None, adapter_bytes=0,
                metrics_sha256="4" * 64, started_at=NOW, finished_at=NOW,
                exit_code=1, network_denied=True, held_out_absent=True,
                base_weights_frozen=False, unexpected_trainable_parameters=(),
                peak_ram_bytes=0, peak_vram_bytes=0,
                maximum_temperature_celsius=0, energy_joules=0,
            )
            self.assertTrue(repositories.training_jobs.record_terminal(receipt))
            self.assertFalse(repositories.training_jobs.record_terminal(receipt))
            database.close()

            database, repositories, _, _ = _repositories(root, seed=False)
            self.assertEqual(job, repositories.training_jobs.get(job.job_id))
            self.assertEqual(receipt, repositories.training_jobs.terminal(job.job_id))
            database.close()


def _environment():
    return build_training_environment(
        environment_id="nvidia-qlora-v1", python_version="3.12.3",
        python_executable_sha256="2" * 64,
        platform="linux-x86_64",
        package_versions=(("bitsandbytes", "0.49.2"), ("torch", "2.13.0")),
        wheelhouse_manifest_sha256="3" * 64,
        worker_script_sha256="4" * 64,
        torch_cuda_version="13.0", nvidia_driver_version="595.71.05",
        device_index=0, device_name="NVIDIA GeForce RTX 5080",
        compute_capability="12.0", total_vram_bytes=16 * GIB,
        cuda_available=True, bfloat16_supported=True,
        bitsandbytes_cuda_available=True, incompatibility_reasons=(),
        observed_at=NOW,
    )


if __name__ == "__main__":
    unittest.main()
