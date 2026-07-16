"""Intel NPU investigation and micro-expert execution evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


NPU_INVESTIGATION_CONTRACT_VERSION = "fam.scheduler.npu-investigation/v1alpha1"


class NpuInvestigationOutcome(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class NpuHardwareEvidence:
    vendor_id: str
    device_id: str
    device_family: str
    kernel_driver: str
    kernel_module_version: str
    operating_system: str
    kernel_release: str
    device_node_present: bool
    host_user_direct_access: bool
    delegated_device_access: bool
    access_mechanism: str

    def __post_init__(self) -> None:
        for name in (
            "vendor_id", "device_id", "device_family", "kernel_driver",
            "kernel_module_version", "operating_system", "kernel_release",
            "access_mechanism",
        ):
            _text(getattr(self, name), name)
        if not self.vendor_id.startswith("0x") or not self.device_id.startswith("0x"):
            raise ValueError("NPU hardware IDs must be hexadecimal")
        if self.delegated_device_access and not self.device_node_present:
            raise ValueError("NPU access cannot exist without a device node")


@dataclass(frozen=True, slots=True)
class NpuRuntimeEvidence:
    runtime_name: str
    runtime_version: str
    user_mode_driver_version: str
    level_zero_version: str
    available_devices: tuple[str, ...]
    npu_full_device_name: str | None
    requested_device: str
    execution_devices: tuple[str, ...]
    cpu_fallback_allowed: bool
    container_isolated: bool

    def __post_init__(self) -> None:
        for name in (
            "runtime_name", "runtime_version", "user_mode_driver_version",
            "level_zero_version", "requested_device",
        ):
            _text(getattr(self, name), name)
        _unique_text(self.available_devices, "available_devices")
        _unique_text(self.execution_devices, "execution_devices")
        if self.requested_device != "NPU" or self.cpu_fallback_allowed:
            raise ValueError("NPU runtime must prohibit CPU fallback")
        if "NPU" in self.available_devices and not self.npu_full_device_name:
            raise ValueError("available NPU requires a full device name")


@dataclass(frozen=True, slots=True)
class NpuMicroExpertEvidence:
    expert_id: str
    capability_id: str
    model_format: str
    model_digest_sha256: str
    input_digest_sha256: str
    output_digest_sha256: str
    expected_label: str
    observed_label: str
    class_labels: tuple[str, ...]
    output_probabilities: tuple[float, ...]
    compile_duration_ms: float
    first_inference_duration_ms: float
    warm_inference_durations_ms: tuple[float, ...]
    fallback_used: bool

    def __post_init__(self) -> None:
        for name in ("expert_id", "capability_id", "model_format", "expected_label", "observed_label"):
            _text(getattr(self, name), name)
        for digest in (self.model_digest_sha256, self.input_digest_sha256, self.output_digest_sha256):
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("NPU evidence digests must be lowercase SHA-256")
        _unique_text(self.class_labels, "class_labels")
        if len(self.output_probabilities) != len(self.class_labels):
            raise ValueError("NPU output dimensions do not match labels")
        if any(not 0 <= value <= 1 for value in self.output_probabilities):
            raise ValueError("NPU probabilities must be within [0, 1]")
        if abs(sum(self.output_probabilities) - 1.0) > 0.01:
            raise ValueError("NPU probabilities must sum to one")
        if self.expected_label != self.observed_label:
            raise ValueError("NPU micro-expert classification failed")
        if self.compile_duration_ms <= 0 or self.first_inference_duration_ms <= 0:
            raise ValueError("NPU compile and first inference timings must be positive")
        if len(self.warm_inference_durations_ms) < 3 or any(value <= 0 for value in self.warm_inference_durations_ms):
            raise ValueError("NPU evidence requires at least three warm inferences")
        if self.fallback_used:
            raise ValueError("CPU fallback cannot prove NPU execution")


@dataclass(frozen=True, slots=True)
class NpuInvestigationReport:
    report_id: str
    started_at: datetime
    completed_at: datetime
    validation_profile_id: str
    outcome: NpuInvestigationOutcome
    hardware: NpuHardwareEvidence
    runtime: NpuRuntimeEvidence
    micro_expert: NpuMicroExpertEvidence | None
    blocking_gate: str | None
    contract_version: str = NPU_INVESTIGATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != NPU_INVESTIGATION_CONTRACT_VERSION:
            raise ValueError("unsupported NPU investigation contract_version")
        _text(self.report_id, "report_id")
        _time(self.started_at, "started_at")
        _time(self.completed_at, "completed_at")
        if self.completed_at <= self.started_at:
            raise ValueError("NPU investigation completion must follow start")
        if self.validation_profile_id != "full-reference-workstation":
            raise ValueError("NPU investigation requires the full workstation profile")
        if self.outcome is NpuInvestigationOutcome.SUPPORTED:
            self._validate_supported()
        elif self.micro_expert is not None or not self.blocking_gate:
            raise ValueError("unsupported NPU report requires one explicit blocking gate")

    def _validate_supported(self) -> None:
        if self.blocking_gate is not None or self.micro_expert is None:
            raise ValueError("supported NPU report requires evidence and no blocking gate")
        if not self.hardware.device_node_present or not self.hardware.delegated_device_access:
            raise ValueError("supported NPU report requires delegated hardware access")
        if "NPU" not in self.runtime.available_devices:
            raise ValueError("supported NPU report requires runtime discovery")
        if self.runtime.execution_devices != ("NPU",):
            raise ValueError("supported NPU report requires NPU-only execution")


def _text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _unique_text(values: tuple[str, ...], name: str) -> None:
    if not values or len(values) != len(set(values)) or any(not value.strip() for value in values):
        raise ValueError(f"{name} must contain unique non-empty values")


def _time(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
