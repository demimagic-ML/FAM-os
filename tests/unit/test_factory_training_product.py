import hashlib
import tempfile
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fam_os.expert_factory import (
    TrainingTerminalStatus,
    build_resource_snapshot,
    build_training_environment,
    build_training_terminal_receipt,
)
from fam_os.product.factory_training import ProductFactoryTraining
from fam_os.product.factory_training_approvals import ProductFactoryTrainingApprovals
from tests.unit.test_factory_training_approval import _issue_values, _repositories


NOW = datetime(2026, 7, 18, tzinfo=UTC)
GIB = 1024**3


class ProductFactoryTrainingTests(unittest.TestCase):
    def test_admission_atomically_consumes_then_records_terminal_backend_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, repositories, proposal_id, dataset = _repositories(
                Path(temporary),
            )
            environment = _environment()
            values = {
                **_issue_values(proposal_id, dataset),
                "environment_sha256": environment.manifest_sha256,
            }
            approval = ProductFactoryTrainingApprovals(
                repositories, now=lambda: NOW,
            ).issue(**values)
            backend = _Backend(repositories, environment)
            product = ProductFactoryTraining(
                repositories, backend, _Observer(False), now=lambda: NOW,
            )
            result = product.start(
                request_id="start-1", approval_id=approval.approval_id,
                confirmed=True,
            )
            self.assertEqual(TrainingTerminalStatus.COMPLETED, result.status)
            self.assertEqual(1, len(repositories.training_approvals.consumptions()))
            self.assertEqual(1, len(product.jobs()))
            self.assertEqual(1, len(product.terminals()))
            self.assertEqual(1, backend.calls)
            database.close()

    def test_denied_resources_do_not_consume_authority_or_create_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, repositories, proposal_id, dataset = _repositories(
                Path(temporary),
            )
            environment = _environment()
            values = {
                **_issue_values(proposal_id, dataset),
                "request_id": "approval-denied",
                "one_use_job_id": "training-job-denied",
                "environment_sha256": environment.manifest_sha256,
            }
            approval = ProductFactoryTrainingApprovals(
                repositories, now=lambda: NOW,
            ).issue(**values)
            backend = _Backend(repositories, environment)
            decision = ProductFactoryTraining(
                repositories, backend, _Observer(True), now=lambda: NOW,
            ).start(
                request_id="start-denied", approval_id=approval.approval_id,
                confirmed=True,
            )
            self.assertFalse(decision.admitted)
            self.assertIn("resource.inference_conflict", decision.reason_codes)
            self.assertEqual((), repositories.training_approvals.consumptions())
            self.assertEqual((), repositories.training_jobs.jobs())
            self.assertEqual(0, backend.calls)
            database.close()

    def test_submit_runs_outside_caller_and_commits_terminal_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, repositories, proposal_id, dataset = _repositories(
                Path(temporary),
            )
            environment = _environment()
            approval = ProductFactoryTrainingApprovals(
                repositories, now=lambda: NOW,
            ).issue(**{
                **_issue_values(proposal_id, dataset),
                "request_id": "approval-background",
                "one_use_job_id": "training-job-background",
                "environment_sha256": environment.manifest_sha256,
            })
            product = ProductFactoryTraining(
                repositories, _Backend(repositories, environment),
                _Observer(False), now=lambda: NOW,
            )
            returned = product.submit(
                approval_id=approval.approval_id, confirmed=True,
            )
            self.assertEqual(approval, returned)
            for _ in range(100):
                if product.terminals():
                    break
                time.sleep(.01)
            product.stop()
            self.assertEqual(TrainingTerminalStatus.COMPLETED, product.terminals()[0].status)
            database.close()


class _Backend:
    def __init__(self, repositories, environment):
        self._repositories = repositories
        self._environment = environment
        self.calls = 0

    def probe(self):
        return self._environment

    def run(self, job):
        self.calls += 1
        self._repositories.training_jobs.mark_running(job.job_id, NOW)
        return build_training_terminal_receipt(
            receipt_id=f"training-terminal-{job.job_id}", job_id=job.job_id,
            approval_id=job.approval_id,
            environment_sha256=job.environment_sha256,
            status=TrainingTerminalStatus.COMPLETED,
            reason_code="training.completed", adapter_sha256="a" * 64,
            adapter_config_sha256="b" * 64, adapter_bytes=1024,
            metrics_sha256=hashlib.sha256(b"metrics").hexdigest(),
            started_at=NOW, finished_at=NOW, exit_code=0,
            network_denied=True, held_out_absent=True, base_weights_frozen=True,
            unexpected_trainable_parameters=(), peak_ram_bytes=GIB,
            peak_vram_bytes=GIB, maximum_temperature_celsius=50,
            energy_joules=10,
        )


class _Observer:
    def __init__(self, conflict: bool):
        self._conflict = conflict

    def observe(self, snapshot_id):
        return build_resource_snapshot(
            snapshot_id=snapshot_id, logical_cpu_count=24, load_fraction=.1,
            available_ram_bytes=60 * GIB, free_disk_bytes=400 * GIB,
            gpu_total_bytes=16 * GIB, gpu_used_bytes=0,
            gpu_utilization_fraction=.05, gpu_temperature_celsius=44,
            inference_conflict=self._conflict, observed_at=NOW,
        )


def _environment():
    return build_training_environment(
        environment_id="nvidia-qlora-v1", python_version="3.12.3",
        python_executable_sha256="1" * 64, platform="linux-x86_64",
        package_versions=(("bitsandbytes", "0.49.2"), ("torch", "2.13.0")),
        wheelhouse_manifest_sha256="2" * 64,
        worker_script_sha256="3" * 64, torch_cuda_version="13.0",
        nvidia_driver_version="595.71.05", device_index=0,
        device_name="NVIDIA GeForce RTX 5080", compute_capability="12.0",
        total_vram_bytes=16 * GIB, cuda_available=True,
        bfloat16_supported=True, bitsandbytes_cuda_available=True,
        incompatibility_reasons=(), observed_at=NOW,
    )


if __name__ == "__main__":
    unittest.main()
