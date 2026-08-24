"""Isolated, resource-monitored NVIDIA QLoRA backend."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fam_os.adapters.training.environment_probe import NvidiaQloraEnvironmentProbe
from fam_os.adapters.training.isolated_command import (
    IsolatedTrainingPaths,
    build_isolated_training_command,
)
from fam_os.expert_factory import (
    AdapterTrainingJob,
    FactoryTrainingApproval,
    TrainingBackendEnvironment,
    TrainingTerminalReceipt,
    TrainingTerminalStatus,
    build_training_terminal_receipt,
)
from fam_os.product.factory_training_workspace import FactoryTrainingWorkspace


@dataclass(frozen=True, slots=True)
class _GpuReading:
    memory_used_bytes: int
    temperature_celsius: int
    power_watts: float


class NvidiaQloraBackend:
    def __init__(
        self, *, repositories, environment_probe: NvidiaQloraEnvironmentProbe,
        workspace: FactoryTrainingWorkspace, environment_directory: Path,
        worker_script: Path, model_directory: Path, now=None,
    ) -> None:
        self._repositories = repositories
        self._environment_probe = environment_probe
        self._workspace = workspace
        self._environment_directory = environment_directory
        self._worker_script = worker_script
        self._model_directory = model_directory
        self._now = now or (lambda: datetime.now(UTC))
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def probe(self) -> TrainingBackendEnvironment:
        return self._environment_probe.probe()

    def run(self, job: AdapterTrainingJob) -> TrainingTerminalReceipt:
        approval = self._approval(job)
        environment = self.probe()
        if not environment.qlora_compatible:
            raise RuntimeError("approved QLoRA environment is incompatible")
        if environment.manifest_sha256 != job.environment_sha256:
            raise PermissionError("training environment changed after admission")
        dataset = self._repositories.sealed_datasets.get(job.dataset_id)
        if dataset is None:
            raise RuntimeError("admitted training dataset is unavailable")
        blobs = self._repositories.sealed_datasets.blobs(job.dataset_id)
        prepared = self._workspace.prepare(
            approval=approval, dataset=dataset, blobs=blobs,
            model_directory=self._model_directory,
        )
        paths = IsolatedTrainingPaths(
            self._environment_directory, self._worker_script,
            self._model_directory, prepared.input_directory,
            prepared.output_directory,
        )
        command = build_isolated_training_command(
            job_id=job.job_id, approval=approval, paths=paths,
        )
        return self._execute(job, approval, prepared.output_directory, command)

    def _execute(
        self, job: AdapterTrainingJob, approval: FactoryTrainingApproval,
        output: Path, command: tuple[str, ...],
    ) -> TrainingTerminalReceipt:
        started = self._now()
        self._repositories.training_jobs.mark_running(job.job_id, started)
        stdout_path, stderr_path = output / "stdout.log", output / "stderr.log"
        unit = f"fam-training-{job.job_id}.scope"
        peak_ram = peak_vram = maximum_temperature = 0
        energy = 0.0
        samples: list[dict[str, int | float]] = []
        stop_reason: str | None = None
        missing_gpu_samples = 0
        monotonic_started = time.monotonic()
        previous_sample = monotonic_started
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
            while process.poll() is None:
                time.sleep(1)
                now_monotonic = time.monotonic()
                reading = _gpu_reading()
                ram = _scope_memory(unit)
                peak_ram = max(peak_ram, ram)
                if reading is not None:
                    missing_gpu_samples = 0
                    peak_vram = max(peak_vram, reading.memory_used_bytes)
                    maximum_temperature = max(
                        maximum_temperature, reading.temperature_celsius,
                    )
                    energy += reading.power_watts * (now_monotonic - previous_sample)
                    samples.append({
                        "elapsed_milliseconds": round(
                            (now_monotonic - monotonic_started) * 1000,
                        ),
                        "memory_bytes": ram,
                        "temperature_celsius": reading.temperature_celsius,
                        "vram_bytes": reading.memory_used_bytes,
                        "watts": reading.power_watts,
                    })
                else:
                    missing_gpu_samples += 1
                previous_sample = now_monotonic
                stop_reason = self._stop_reason(
                    job, approval, output, peak_ram, peak_vram,
                    maximum_temperature, energy, now_monotonic - monotonic_started,
                )
                if stop_reason is None and missing_gpu_samples >= 3:
                    stop_reason = "training.gpu_telemetry_unavailable"
                if stop_reason is not None:
                    _stop_unit(unit, process)
                    break
            exit_code = process.wait(timeout=30)
        finished = self._now()
        worker = _worker_result(output)
        artifact_error = _validate_completed_artifacts(output, worker)
        if artifact_error is not None and stop_reason is None:
            worker = {
                "reason_code": artifact_error,
                "status": "failed",
                "worker_metrics_sha256": worker.get("metrics_sha256"),
            }
        status, reason = _status(worker, exit_code, stop_reason)
        metrics_path = output / "resource-metrics.json"
        metrics_path.write_text(json.dumps({
            "samples": samples,
            "worker_metrics_sha256": worker.get("metrics_sha256"),
        }, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        completed = status is TrainingTerminalStatus.COMPLETED
        held_out_absent = _held_out_absent(output.parent / "input")
        receipt = build_training_terminal_receipt(
            receipt_id=f"training-terminal-{job.job_id}", job_id=job.job_id,
            approval_id=job.approval_id,
            environment_sha256=job.environment_sha256, status=status,
            reason_code=reason,
            adapter_sha256=_optional_sha(worker, "adapter_sha256") if completed else None,
            adapter_config_sha256=(
                _optional_sha(worker, "adapter_config_sha256") if completed else None
            ),
            adapter_bytes=_integer(worker, "adapter_bytes") if completed else 0,
            metrics_sha256=_file_sha256(metrics_path), started_at=started,
            finished_at=finished, exit_code=exit_code,
            network_denied="--unshare-all" in command and "--share-net" not in command,
            held_out_absent=held_out_absent,
            base_weights_frozen=(worker.get("base_weights_frozen") is True),
            unexpected_trainable_parameters=tuple(
                str(item) for item in worker.get("unexpected_trainable_parameters", ())
            ),
            peak_ram_bytes=peak_ram, peak_vram_bytes=peak_vram,
            maximum_temperature_celsius=maximum_temperature,
            energy_joules=round(energy),
        )
        return receipt

    def _approval(self, job: AdapterTrainingJob) -> FactoryTrainingApproval:
        approval = self._repositories.training_approvals.get(job.approval_id)
        if approval is None or approval.one_use_job_id != job.job_id:
            raise PermissionError("training job approval is unavailable")
        return approval

    def _stop_reason(
        self, job, approval, output, ram, vram, temperature, energy, elapsed,
    ) -> str | None:
        if not self._repositories.training_approvals.is_active(
            job.approval_id, job.approval_revision, self._now(),
        ):
            return "training.approval_revoked"
        if self._stop.is_set():
            return "training.service_stopped"
        if elapsed > approval.maximum_wall_seconds:
            return "training.wall_time_exceeded"
        if ram > approval.resources.maximum_ram_bytes:
            return "training.ram_exceeded"
        if vram > approval.resources.maximum_vram_bytes:
            return "training.vram_exceeded"
        if temperature > approval.resources.maximum_temperature_celsius:
            return "training.temperature_exceeded"
        if energy > approval.resources.maximum_energy_joules:
            return "training.energy_exceeded"
        if _directory_bytes(output) > approval.maximum_output_bytes:
            return "training.output_exceeded"
        if _checkpoint_bytes(output) > approval.maximum_checkpoint_bytes:
            return "training.checkpoint_exceeded"
        return None


def _gpu_reading() -> _GpuReading | None:
    result = subprocess.run((
        "nvidia-smi",
        "--query-gpu=memory.used,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ), check=False, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        return None
    try:
        memory, temperature, power = (
            value.strip() for value in result.stdout.splitlines()[0].split(",")
        )
        return _GpuReading(int(memory) * 1024**2, int(temperature), float(power))
    except (IndexError, ValueError):
        return None


def _scope_memory(unit: str) -> int:
    result = subprocess.run(
        ("systemctl", "--user", "show", unit, "-p", "MemoryCurrent", "--value"),
        check=False, capture_output=True, text=True, timeout=10,
    )
    try:
        return int(result.stdout.strip()) if result.returncode == 0 else 0
    except ValueError:
        return 0


def _stop_unit(unit: str, process: subprocess.Popen[bytes]) -> None:
    subprocess.run(
        ("systemctl", "--user", "kill", "--signal=TERM", unit),
        check=False, capture_output=True, timeout=10,
    )
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()


def _worker_result(output: Path) -> dict:
    path = output / "worker-result.json"
    if (
        not path.is_file() or path.is_symlink()
        or path.stat().st_size > 64 * 1024
    ):
        return {}
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _status(worker: dict, exit_code: int, stop_reason: str | None):
    if stop_reason is not None:
        status = (
            TrainingTerminalStatus.REVOKED
            if stop_reason == "training.approval_revoked"
            else TrainingTerminalStatus.RESOURCE_STOPPED
        )
        return status, stop_reason
    if exit_code == 0 and worker.get("status") == "completed":
        return TrainingTerminalStatus.COMPLETED, "training.completed"
    return TrainingTerminalStatus.FAILED, str(
        worker.get("reason_code", "training.worker_failed"),
    )


def _optional_sha(document: dict, name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str) or len(value) != 64:
        raise RuntimeError(f"completed worker has invalid {name}")
    return value


def _integer(document: dict, name: str) -> int:
    value = document.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise RuntimeError(f"completed worker has invalid {name}")
    return value


def _directory_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _checkpoint_bytes(path: Path) -> int:
    return sum(
        _directory_bytes(item) for item in path.rglob("checkpoint-*")
        if item.is_dir() and not item.is_symlink()
    )


def _held_out_absent(path: Path) -> bool:
    try:
        entries = tuple(path.iterdir())
    except OSError:
        return False
    return (
        {item.name for item in entries}
        == {"config.json", "train.jsonl", "validation.jsonl"}
        and all(item.is_file() and not item.is_symlink() for item in entries)
    )


def _validate_completed_artifacts(output: Path, worker: dict) -> str | None:
    if worker.get("status") != "completed":
        return None
    expected = {
        "adapter_bytes", "adapter_config_sha256", "adapter_sha256",
        "base_weights_frozen", "duration_seconds", "metrics_sha256",
        "reason_code", "status", "unexpected_trainable_parameters",
    }
    if set(worker) != expected:
        return "training.worker_result_invalid"
    adapter = output / "adapter"
    metrics = output / "metrics.json"
    config = adapter / "adapter_config.json"
    if any(
        not path.is_file() or path.is_symlink() for path in (metrics, config)
    ) or not adapter.is_dir() or adapter.is_symlink():
        return "training.artifact_missing"
    try:
        if _file_sha256(metrics) != _optional_sha(worker, "metrics_sha256"):
            return "training.metrics_digest_mismatch"
        if _file_sha256(config) != _optional_sha(worker, "adapter_config_sha256"):
            return "training.adapter_config_digest_mismatch"
        if _directory_manifest_sha256(adapter) != _optional_sha(
            worker, "adapter_sha256",
        ):
            return "training.adapter_digest_mismatch"
        if _directory_bytes(adapter) != _integer(worker, "adapter_bytes"):
            return "training.adapter_size_mismatch"
    except (OSError, RuntimeError, ValueError):
        return "training.artifact_invalid"
    return None


def _directory_manifest_sha256(path: Path) -> str:
    records = []
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise ValueError("training artifacts cannot contain symlinks")
        if item.is_file():
            records.append((item.relative_to(path).as_posix(), _file_sha256(item)))
    if not records:
        raise ValueError("training adapter is empty")
    return hashlib.sha256(
        json.dumps(records, separators=(",", ":")).encode(),
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
