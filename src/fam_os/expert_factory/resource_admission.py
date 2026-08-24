"""Fail-closed live resource admission for a bounded training job."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from fam_os.expert_factory.training_approval import TrainingResourceBudget


FACTORY_RESOURCE_ADMISSION_VERSION = "fam.factory.resource-admission/v1alpha1"


@dataclass(frozen=True, slots=True)
class TrainingResourceSnapshot:
    snapshot_id: str
    logical_cpu_count: int
    load_fraction: float
    available_ram_bytes: int
    free_disk_bytes: int
    gpu_total_bytes: int
    gpu_used_bytes: int
    gpu_utilization_fraction: float
    gpu_temperature_celsius: int
    inference_conflict: bool
    observed_at: datetime
    snapshot_sha256: str
    contract_version: str = FACTORY_RESOURCE_ADMISSION_VERSION

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip() or self.logical_cpu_count < 1:
            raise ValueError("training resource snapshot identity is invalid")
        if not 0 <= self.load_fraction <= 100:
            raise ValueError("training load fraction is invalid")
        for name in (
            "available_ram_bytes", "free_disk_bytes", "gpu_total_bytes",
            "gpu_used_bytes", "gpu_temperature_celsius",
        ):
            if getattr(self, name) < 0:
                raise ValueError("training resource reading cannot be negative")
        if self.gpu_used_bytes > self.gpu_total_bytes:
            raise ValueError("training GPU memory reading is invalid")
        if not 0 <= self.gpu_utilization_fraction <= 1:
            raise ValueError("training GPU utilization is invalid")
        _aware(self.observed_at)
        _sha(self.snapshot_sha256)
        if self.snapshot_sha256 != resource_snapshot_digest(self):
            raise ValueError("training resource snapshot digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class TrainingAdmissionDecision:
    decision_id: str
    approval_id: str
    snapshot_sha256: str
    admitted: bool
    reason_codes: tuple[str, ...]
    decided_at: datetime
    decision_sha256: str
    contract_version: str = FACTORY_RESOURCE_ADMISSION_VERSION

    def __post_init__(self) -> None:
        if not self.decision_id.strip() or not self.approval_id.strip():
            raise ValueError("training admission identity is invalid")
        _sha(self.snapshot_sha256)
        if self.admitted == bool(self.reason_codes):
            raise ValueError("training admission reasons are inconsistent")
        if self.reason_codes != tuple(sorted(set(self.reason_codes))):
            raise ValueError("training admission reasons must be sorted and unique")
        _aware(self.decided_at)
        _sha(self.decision_sha256)
        if self.decision_sha256 != admission_decision_digest(self):
            raise ValueError("training admission decision digest does not match")
        _version(self.contract_version)


def decide_training_admission(
    *, decision_id: str, approval_id: str, budget: TrainingResourceBudget,
    snapshot: TrainingResourceSnapshot, decided_at: datetime,
) -> TrainingAdmissionDecision:
    reasons = []
    if budget.maximum_cpu_cores > snapshot.logical_cpu_count:
        reasons.append("resource.cpu_insufficient")
    if budget.maximum_ram_bytes > snapshot.available_ram_bytes:
        reasons.append("resource.ram_insufficient")
    if budget.maximum_disk_bytes > snapshot.free_disk_bytes:
        reasons.append("resource.disk_insufficient")
    if budget.maximum_vram_bytes > (
        snapshot.gpu_total_bytes - snapshot.gpu_used_bytes
    ):
        reasons.append("resource.vram_insufficient")
    if snapshot.gpu_temperature_celsius > budget.maximum_temperature_celsius - 5:
        reasons.append("resource.thermal_headroom_insufficient")
    if snapshot.gpu_utilization_fraction > 0.30:
        reasons.append("resource.gpu_foreground_pressure")
    if snapshot.load_fraction > 0.75:
        reasons.append("resource.cpu_foreground_pressure")
    if snapshot.inference_conflict:
        reasons.append("resource.inference_conflict")
    reasons_tuple = tuple(sorted(reasons))
    document = {
        "admitted": not reasons_tuple, "approval_id": approval_id,
        "decided_at": decided_at.isoformat(), "decision_id": decision_id,
        "reason_codes": reasons_tuple,
        "snapshot_sha256": snapshot.snapshot_sha256,
    }
    return TrainingAdmissionDecision(
        decision_id, approval_id, snapshot.snapshot_sha256, not reasons_tuple,
        reasons_tuple, decided_at, _digest(document),
    )


def build_resource_snapshot(
    *, snapshot_id: str, logical_cpu_count: int, load_fraction: float,
    available_ram_bytes: int, free_disk_bytes: int, gpu_total_bytes: int,
    gpu_used_bytes: int, gpu_utilization_fraction: float,
    gpu_temperature_celsius: int, inference_conflict: bool,
    observed_at: datetime,
) -> TrainingResourceSnapshot:
    document = {
        "available_ram_bytes": available_ram_bytes,
        "free_disk_bytes": free_disk_bytes, "gpu_total_bytes": gpu_total_bytes,
        "gpu_temperature_celsius": gpu_temperature_celsius,
        "gpu_used_bytes": gpu_used_bytes,
        "gpu_utilization_fraction": gpu_utilization_fraction,
        "inference_conflict": inference_conflict,
        "load_fraction": load_fraction, "logical_cpu_count": logical_cpu_count,
        "observed_at": observed_at.isoformat(), "snapshot_id": snapshot_id,
    }
    return TrainingResourceSnapshot(
        snapshot_id, logical_cpu_count, load_fraction, available_ram_bytes,
        free_disk_bytes, gpu_total_bytes, gpu_used_bytes,
        gpu_utilization_fraction, gpu_temperature_celsius, inference_conflict,
        observed_at, _digest(document),
    )


def resource_snapshot_digest(value: TrainingResourceSnapshot) -> str:
    return _digest({
        "available_ram_bytes": value.available_ram_bytes,
        "free_disk_bytes": value.free_disk_bytes,
        "gpu_total_bytes": value.gpu_total_bytes,
        "gpu_temperature_celsius": value.gpu_temperature_celsius,
        "gpu_used_bytes": value.gpu_used_bytes,
        "gpu_utilization_fraction": value.gpu_utilization_fraction,
        "inference_conflict": value.inference_conflict,
        "load_fraction": value.load_fraction,
        "logical_cpu_count": value.logical_cpu_count,
        "observed_at": value.observed_at.isoformat(),
        "snapshot_id": value.snapshot_id,
    })


def admission_decision_digest(value: TrainingAdmissionDecision) -> str:
    return _digest({
        "admitted": value.admitted, "approval_id": value.approval_id,
        "decided_at": value.decided_at.isoformat(),
        "decision_id": value.decision_id, "reason_codes": value.reason_codes,
        "snapshot_sha256": value.snapshot_sha256,
    })


def _digest(document: object) -> str:
    return hashlib.sha256(json.dumps(
        document, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def _sha(value: str) -> None:
    if len(value) != 64 or any(item not in "0123456789abcdef" for item in value):
        raise ValueError("resource evidence digest must be lowercase SHA-256")


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("resource evidence time must be timezone-aware")


def _version(value: str) -> None:
    if value != FACTORY_RESOURCE_ADMISSION_VERSION:
        raise ValueError("unsupported resource admission contract version")
