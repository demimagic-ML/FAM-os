"""Immutable contracts for isolated real adapter training."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


FACTORY_TRAINING_BACKEND_VERSION = "fam.factory.training-backend/v1alpha1"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


class TrainingTerminalStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVOKED = "revoked"
    RESOURCE_STOPPED = "resource_stopped"


@dataclass(frozen=True, slots=True)
class TrainingBackendEnvironment:
    environment_id: str
    python_version: str
    python_executable_sha256: str
    platform: str
    package_versions: tuple[tuple[str, str], ...]
    wheelhouse_manifest_sha256: str
    worker_script_sha256: str
    torch_cuda_version: str
    nvidia_driver_version: str
    device_index: int
    device_name: str
    compute_capability: str
    total_vram_bytes: int
    cuda_available: bool
    bfloat16_supported: bool
    bitsandbytes_cuda_available: bool
    qlora_compatible: bool
    incompatibility_reasons: tuple[str, ...]
    manifest_sha256: str
    observed_at: datetime
    contract_version: str = FACTORY_TRAINING_BACKEND_VERSION

    def __post_init__(self) -> None:
        _identifier(self.environment_id, "environment_id")
        for value in (
            self.python_version, self.platform, self.torch_cuda_version,
            self.nvidia_driver_version, self.device_name, self.compute_capability,
        ):
            if not value.strip() or len(value) > 512:
                raise ValueError("training environment identity is invalid")
        if (
            not self.package_versions
            or self.package_versions != tuple(sorted(set(self.package_versions)))
            or any(not name.strip() or not version.strip() for name, version in self.package_versions)
        ):
            raise ValueError("training environment packages must be sorted and unique")
        _sha256(self.python_executable_sha256, "python_executable_sha256")
        _sha256(self.wheelhouse_manifest_sha256, "wheelhouse_manifest_sha256")
        _sha256(self.worker_script_sha256, "worker_script_sha256")
        if self.device_index < 0 or self.total_vram_bytes < 256 * 1024 * 1024:
            raise ValueError("training environment GPU values are invalid")
        if self.qlora_compatible != (
            self.cuda_available and self.bitsandbytes_cuda_available
        ):
            raise ValueError("training environment compatibility is inconsistent")
        if self.qlora_compatible == bool(self.incompatibility_reasons):
            raise ValueError("training environment incompatibility reasons are inconsistent")
        _sha256(self.manifest_sha256, "manifest_sha256")
        if self.manifest_sha256 != training_environment_digest(self):
            raise ValueError("training environment manifest digest does not match")
        _aware(self.observed_at, "observed_at")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class AdapterTrainingJob:
    job_id: str
    approval_id: str
    approval_revision: int
    approval_consumption_receipt_id: str
    proposal_id: str
    capability_id: str
    dataset_id: str
    dataset_manifest_sha256: str
    train_blob_sha256: str
    validation_blob_sha256: str
    base_model_files_sha256: str
    environment_sha256: str
    held_out_excluded: bool
    admitted_at: datetime
    job_sha256: str
    contract_version: str = FACTORY_TRAINING_BACKEND_VERSION

    def __post_init__(self) -> None:
        for name in (
            "job_id", "approval_id", "approval_consumption_receipt_id",
            "proposal_id", "capability_id", "dataset_id",
        ):
            _identifier(getattr(self, name), name)
        if self.approval_revision < 1:
            raise ValueError("training job approval revision is invalid")
        for name in (
            "dataset_manifest_sha256", "train_blob_sha256",
            "validation_blob_sha256", "base_model_files_sha256",
            "environment_sha256", "job_sha256",
        ):
            _sha256(getattr(self, name), name)
        if not self.held_out_excluded:
            raise ValueError("training jobs must exclude held-out content")
        _aware(self.admitted_at, "admitted_at")
        if self.job_sha256 != training_job_digest(self):
            raise ValueError("training job digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class TrainingTerminalReceipt:
    receipt_id: str
    job_id: str
    approval_id: str
    environment_sha256: str
    status: TrainingTerminalStatus
    reason_code: str
    adapter_sha256: str | None
    adapter_config_sha256: str | None
    adapter_bytes: int
    metrics_sha256: str
    started_at: datetime
    finished_at: datetime
    exit_code: int
    network_denied: bool
    held_out_absent: bool
    base_weights_frozen: bool
    unexpected_trainable_parameters: tuple[str, ...]
    peak_ram_bytes: int
    peak_vram_bytes: int
    maximum_temperature_celsius: int
    energy_joules: int
    receipt_sha256: str
    contract_version: str = FACTORY_TRAINING_BACKEND_VERSION

    def __post_init__(self) -> None:
        for name in ("receipt_id", "job_id", "approval_id", "reason_code"):
            _identifier(getattr(self, name), name)
        if not isinstance(self.status, TrainingTerminalStatus):
            raise ValueError("training terminal status is invalid")
        for name in ("environment_sha256", "metrics_sha256", "receipt_sha256"):
            _sha256(getattr(self, name), name)
        completed = self.status is TrainingTerminalStatus.COMPLETED
        if completed != (self.adapter_sha256 is not None):
            raise ValueError("training artifact presence is inconsistent")
        if completed != (self.adapter_config_sha256 is not None):
            raise ValueError("training adapter config presence is inconsistent")
        for value in (self.adapter_sha256, self.adapter_config_sha256):
            if value is not None:
                _sha256(value, "adapter artifact digest")
        if self.adapter_bytes < 0 or completed != (self.adapter_bytes > 0):
            raise ValueError("training adapter size is inconsistent")
        _aware(self.started_at, "started_at")
        _aware(self.finished_at, "finished_at")
        if self.finished_at < self.started_at:
            raise ValueError("training receipt time range is invalid")
        if completed and self.exit_code != 0:
            raise ValueError("completed training must have a zero exit code")
        if completed and (not self.network_denied or not self.held_out_absent):
            raise ValueError("completed training isolation evidence is incomplete")
        if completed and (
            not self.base_weights_frozen or self.unexpected_trainable_parameters
        ):
            raise ValueError("completed adapter training changed unapproved parameters")
        for name in (
            "peak_ram_bytes", "peak_vram_bytes", "maximum_temperature_celsius",
            "energy_joules",
        ):
            if getattr(self, name) < 0:
                raise ValueError("training resource evidence cannot be negative")
        if self.receipt_sha256 != training_terminal_receipt_digest(self):
            raise ValueError("training terminal receipt digest does not match")
        _version(self.contract_version)


def build_training_environment(
    *, environment_id: str, python_version: str, python_executable_sha256: str,
    platform: str, package_versions: tuple[tuple[str, str], ...],
    wheelhouse_manifest_sha256: str, worker_script_sha256: str,
    torch_cuda_version: str,
    nvidia_driver_version: str, device_index: int, device_name: str,
    compute_capability: str, total_vram_bytes: int, cuda_available: bool,
    bfloat16_supported: bool, bitsandbytes_cuda_available: bool,
    incompatibility_reasons: tuple[str, ...], observed_at: datetime,
) -> TrainingBackendEnvironment:
    compatible = cuda_available and bitsandbytes_cuda_available
    document = {
        "bfloat16_supported": bfloat16_supported,
        "bitsandbytes_cuda_available": bitsandbytes_cuda_available,
        "compute_capability": compute_capability,
        "cuda_available": cuda_available, "device_index": device_index,
        "device_name": device_name, "environment_id": environment_id,
        "incompatibility_reasons": incompatibility_reasons,
        "nvidia_driver_version": nvidia_driver_version,
        "package_versions": package_versions, "platform": platform,
        "python_executable_sha256": python_executable_sha256,
        "python_version": python_version, "qlora_compatible": compatible,
        "torch_cuda_version": torch_cuda_version,
        "total_vram_bytes": total_vram_bytes,
        "wheelhouse_manifest_sha256": wheelhouse_manifest_sha256,
        "worker_script_sha256": worker_script_sha256,
    }
    return TrainingBackendEnvironment(
        environment_id, python_version, python_executable_sha256, platform,
        package_versions, wheelhouse_manifest_sha256, worker_script_sha256,
        torch_cuda_version, nvidia_driver_version, device_index, device_name,
        compute_capability, total_vram_bytes, cuda_available,
        bfloat16_supported, bitsandbytes_cuda_available, compatible,
        incompatibility_reasons, _digest(document), observed_at,
    )


def build_training_job(
    *, job_id: str, approval_id: str, approval_revision: int,
    approval_consumption_receipt_id: str, proposal_id: str, capability_id: str,
    dataset_id: str, dataset_manifest_sha256: str, train_blob_sha256: str,
    validation_blob_sha256: str, base_model_files_sha256: str,
    environment_sha256: str, admitted_at: datetime,
) -> AdapterTrainingJob:
    values = (
        job_id, approval_id, approval_revision, approval_consumption_receipt_id,
        proposal_id, capability_id, dataset_id, dataset_manifest_sha256,
        train_blob_sha256, validation_blob_sha256, base_model_files_sha256,
        environment_sha256, True, admitted_at,
    )
    document = {
        "admitted_at": admitted_at.isoformat(),
        "approval_consumption_receipt_id": approval_consumption_receipt_id,
        "approval_id": approval_id, "approval_revision": approval_revision,
        "base_model_files_sha256": base_model_files_sha256,
        "capability_id": capability_id, "dataset_id": dataset_id,
        "dataset_manifest_sha256": dataset_manifest_sha256,
        "environment_sha256": environment_sha256, "held_out_excluded": True,
        "job_id": job_id, "proposal_id": proposal_id,
        "train_blob_sha256": train_blob_sha256,
        "validation_blob_sha256": validation_blob_sha256,
    }
    return AdapterTrainingJob(*values, _digest(document))


def build_training_terminal_receipt(
    *, receipt_id: str, job_id: str, approval_id: str,
    environment_sha256: str, status: TrainingTerminalStatus, reason_code: str,
    adapter_sha256: str | None, adapter_config_sha256: str | None,
    adapter_bytes: int, metrics_sha256: str, started_at: datetime,
    finished_at: datetime, exit_code: int, network_denied: bool,
    held_out_absent: bool, base_weights_frozen: bool,
    unexpected_trainable_parameters: tuple[str, ...], peak_ram_bytes: int,
    peak_vram_bytes: int, maximum_temperature_celsius: int,
    energy_joules: int,
) -> TrainingTerminalReceipt:
    values = (
        receipt_id, job_id, approval_id, environment_sha256, status, reason_code,
        adapter_sha256, adapter_config_sha256, adapter_bytes, metrics_sha256,
        started_at, finished_at, exit_code, network_denied, held_out_absent,
        base_weights_frozen, unexpected_trainable_parameters, peak_ram_bytes,
        peak_vram_bytes, maximum_temperature_celsius, energy_joules,
    )
    document = {
        "adapter_bytes": adapter_bytes,
        "adapter_config_sha256": adapter_config_sha256,
        "adapter_sha256": adapter_sha256, "approval_id": approval_id,
        "base_weights_frozen": base_weights_frozen,
        "energy_joules": energy_joules,
        "environment_sha256": environment_sha256, "exit_code": exit_code,
        "finished_at": finished_at.isoformat(), "held_out_absent": held_out_absent,
        "job_id": job_id,
        "maximum_temperature_celsius": maximum_temperature_celsius,
        "metrics_sha256": metrics_sha256, "network_denied": network_denied,
        "peak_ram_bytes": peak_ram_bytes, "peak_vram_bytes": peak_vram_bytes,
        "reason_code": reason_code, "receipt_id": receipt_id,
        "started_at": started_at.isoformat(), "status": status.value,
        "unexpected_trainable_parameters": unexpected_trainable_parameters,
    }
    return TrainingTerminalReceipt(*values, _digest(document))


def training_environment_digest(value: TrainingBackendEnvironment) -> str:
    return _digest({
        "bfloat16_supported": value.bfloat16_supported,
        "bitsandbytes_cuda_available": value.bitsandbytes_cuda_available,
        "compute_capability": value.compute_capability,
        "cuda_available": value.cuda_available,
        "device_index": value.device_index,
        "device_name": value.device_name,
        "environment_id": value.environment_id,
        "incompatibility_reasons": value.incompatibility_reasons,
        "nvidia_driver_version": value.nvidia_driver_version,
        "package_versions": value.package_versions,
        "platform": value.platform,
        "python_executable_sha256": value.python_executable_sha256,
        "python_version": value.python_version,
        "qlora_compatible": value.qlora_compatible,
        "torch_cuda_version": value.torch_cuda_version,
        "total_vram_bytes": value.total_vram_bytes,
        "wheelhouse_manifest_sha256": value.wheelhouse_manifest_sha256,
        "worker_script_sha256": value.worker_script_sha256,
    })


def training_job_digest(value: AdapterTrainingJob) -> str:
    return _digest({
        "admitted_at": value.admitted_at.isoformat(),
        "approval_consumption_receipt_id": value.approval_consumption_receipt_id,
        "approval_id": value.approval_id,
        "approval_revision": value.approval_revision,
        "base_model_files_sha256": value.base_model_files_sha256,
        "capability_id": value.capability_id,
        "dataset_id": value.dataset_id,
        "dataset_manifest_sha256": value.dataset_manifest_sha256,
        "environment_sha256": value.environment_sha256,
        "held_out_excluded": value.held_out_excluded,
        "job_id": value.job_id,
        "proposal_id": value.proposal_id,
        "train_blob_sha256": value.train_blob_sha256,
        "validation_blob_sha256": value.validation_blob_sha256,
    })


def training_terminal_receipt_digest(value: TrainingTerminalReceipt) -> str:
    return _digest({
        name: (
            field.isoformat() if isinstance(field, datetime)
            else field.value if isinstance(field, StrEnum) else field
        )
        for name, field in (
            ("adapter_bytes", value.adapter_bytes),
            ("adapter_config_sha256", value.adapter_config_sha256),
            ("adapter_sha256", value.adapter_sha256),
            ("approval_id", value.approval_id),
            ("base_weights_frozen", value.base_weights_frozen),
            ("energy_joules", value.energy_joules),
            ("environment_sha256", value.environment_sha256),
            ("exit_code", value.exit_code),
            ("finished_at", value.finished_at),
            ("held_out_absent", value.held_out_absent),
            ("job_id", value.job_id),
            ("maximum_temperature_celsius", value.maximum_temperature_celsius),
            ("metrics_sha256", value.metrics_sha256),
            ("network_denied", value.network_denied),
            ("peak_ram_bytes", value.peak_ram_bytes),
            ("peak_vram_bytes", value.peak_vram_bytes),
            ("reason_code", value.reason_code),
            ("receipt_id", value.receipt_id),
            ("started_at", value.started_at),
            ("status", value.status),
            ("unexpected_trainable_parameters", value.unexpected_trainable_parameters),
        )
    })


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} is invalid")


def _sha256(value: str, name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be lowercase SHA-256")


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _version(value: str) -> None:
    if value != FACTORY_TRAINING_BACKEND_VERSION:
        raise ValueError("unsupported training backend contract version")
