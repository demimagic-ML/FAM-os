"""Owner-confirmed admission and execution of one real factory training job."""

from __future__ import annotations

import hashlib
import logging
import threading
from datetime import UTC, datetime

from fam_os.expert_factory import (
    AdapterTrainingJob,
    DatasetPartition,
    TrainingAdmissionDecision,
    TrainingBackendEnvironment,
    TrainingTerminalReceipt,
    TrainingTerminalStatus,
    build_training_job,
    build_training_terminal_receipt,
    decide_training_admission,
)


LOGGER = logging.getLogger(__name__)


class ProductFactoryTraining:
    def __init__(self, repositories, backend, resource_observer, now=None) -> None:
        self._repositories = repositories
        self._backend = backend
        self._resource_observer = resource_observer
        self._now = now or (lambda: datetime.now(UTC))
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}

    def submit(self, *, approval_id: str, confirmed: bool):
        if not confirmed:
            raise PermissionError("real training requires confirmation")
        approval = self._repositories.training_approvals.get(approval_id)
        if approval is None:
            raise KeyError("training approval is unavailable")
        terminal = self._repositories.training_jobs.terminal(approval.one_use_job_id)
        if terminal is not None:
            return terminal
        if self._repositories.training_jobs.get(approval.one_use_job_id) is not None:
            raise RuntimeError("training job is nonterminal and requires reconciliation")
        with self._lock:
            thread = self._threads.get(approval.one_use_job_id)
            if thread is not None and thread.is_alive():
                return approval
            thread = threading.Thread(
                target=self._background_start,
                args=(approval.one_use_job_id, approval.approval_id),
                daemon=True,
                name=f"fam-training-{approval.one_use_job_id}",
            )
            self._threads[approval.one_use_job_id] = thread
            thread.start()
        return approval

    def stop(self) -> None:
        stop = getattr(self._backend, "stop", None)
        if callable(stop):
            stop()
        with self._lock:
            threads = tuple(self._threads.values())
        for thread in threads:
            thread.join(timeout=30)

    def _background_start(self, job_id: str, approval_id: str) -> None:
        try:
            self.start(
                request_id=f"background-{job_id}", approval_id=approval_id,
                confirmed=True,
            )
        except Exception:
            LOGGER.exception("background factory training failed for %s", job_id)
        finally:
            with self._lock:
                self._threads.pop(job_id, None)

    def probe_environment(self) -> TrainingBackendEnvironment:
        environment = self._backend.probe()
        self._repositories.training_jobs.add_environment(environment)
        return environment

    def start(
        self, *, request_id: str, approval_id: str, confirmed: bool,
    ) -> TrainingTerminalReceipt | TrainingAdmissionDecision:
        if not confirmed:
            raise PermissionError("real training requires confirmation")
        approval = self._repositories.training_approvals.get(approval_id)
        if approval is None:
            raise KeyError("training approval is unavailable")
        terminal = self._repositories.training_jobs.terminal(approval.one_use_job_id)
        if terminal is not None:
            return terminal
        if self._repositories.training_jobs.get(approval.one_use_job_id) is not None:
            raise RuntimeError(
                "training job is nonterminal and requires explicit recovery",
            )
        environment = self.probe_environment()
        if not environment.qlora_compatible:
            raise RuntimeError("NVIDIA QLoRA environment is incompatible")
        if environment.manifest_sha256 != approval.environment_sha256:
            raise PermissionError("training environment does not match approval")
        dataset = self._repositories.sealed_datasets.get(approval.sealed_dataset_id)
        if dataset is None or dataset.manifest_sha256 != approval.sealed_dataset_sha256:
            raise PermissionError("sealed training dataset does not match approval")
        blobs = self._repositories.sealed_datasets.blobs(dataset.dataset_id)
        by_partition = {item.partition: item for item in blobs}
        if set(by_partition) != set(DatasetPartition):
            raise PermissionError("sealed training dataset blobs are incomplete")
        now = self._now()
        snapshot = self._resource_observer.observe(
            f"training-resource-{request_id}",
        )
        decision = decide_training_admission(
            decision_id=f"training-admission-{request_id}",
            approval_id=approval.approval_id, budget=approval.resources,
            snapshot=snapshot, decided_at=now,
        )
        self._repositories.training_admissions.record(snapshot, decision)
        if not decision.admitted:
            return decision
        job = build_training_job(
            job_id=approval.one_use_job_id, approval_id=approval.approval_id,
            approval_revision=approval.revision,
            approval_consumption_receipt_id=(
                f"training-consumption-{approval.approval_id}"
            ),
            proposal_id=approval.proposal_id,
            capability_id=approval.capability_id, dataset_id=dataset.dataset_id,
            dataset_manifest_sha256=dataset.manifest_sha256,
            train_blob_sha256=(
                by_partition[DatasetPartition.TRAIN].plaintext_sha256
            ),
            validation_blob_sha256=(
                by_partition[DatasetPartition.VALIDATION].plaintext_sha256
            ),
            base_model_files_sha256=approval.base_model.files_manifest_sha256,
            environment_sha256=environment.manifest_sha256, admitted_at=now,
        )
        self._repositories.training_jobs.admit(job, now)
        try:
            receipt = self._backend.run(job)
            self._repositories.training_jobs.record_terminal(receipt)
            return receipt
        except Exception as error:
            existing = self._repositories.training_jobs.terminal(job.job_id)
            if existing is not None:
                return existing
            finished = self._now()
            receipt = build_training_terminal_receipt(
                receipt_id=f"training-terminal-{job.job_id}", job_id=job.job_id,
                approval_id=approval.approval_id,
                environment_sha256=environment.manifest_sha256,
                status=TrainingTerminalStatus.FAILED,
                reason_code=f"training.backend_{type(error).__name__.lower()}",
                adapter_sha256=None, adapter_config_sha256=None,
                adapter_bytes=0, metrics_sha256=hashlib.sha256(b"{}").hexdigest(),
                started_at=now, finished_at=finished, exit_code=1,
                network_denied=False, held_out_absent=False,
                base_weights_frozen=False, unexpected_trainable_parameters=(),
                peak_ram_bytes=0, peak_vram_bytes=0,
                maximum_temperature_celsius=0, energy_joules=0,
            )
            self._repositories.training_jobs.record_terminal(receipt)
            return receipt

    def jobs(self) -> tuple[AdapterTrainingJob, ...]:
        return self._repositories.training_jobs.jobs()

    def terminals(self) -> tuple[TrainingTerminalReceipt, ...]:
        return self._repositories.training_jobs.terminals()

    def admissions(self) -> tuple[TrainingAdmissionDecision, ...]:
        return self._repositories.training_admissions.decisions()
