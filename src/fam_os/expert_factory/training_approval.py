"""Six-dimensional one-use authority for real adapter training."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


FACTORY_TRAINING_APPROVAL_VERSION = "fam.factory.training-approval/v1alpha1"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


class AdapterTrainingMethod(StrEnum):
    LORA = "lora"
    QLORA = "qlora"


class TrainingComputeDtype(StrEnum):
    BFLOAT16 = "bfloat16"
    FLOAT16 = "float16"


@dataclass(frozen=True, slots=True)
class ApprovedBaseModel:
    repository_id: str
    revision: str
    tokenizer_id: str
    tokenizer_revision: str
    license_id: str
    files_manifest_sha256: str
    contract_version: str = FACTORY_TRAINING_APPROVAL_VERSION

    def __post_init__(self) -> None:
        for name in ("repository_id", "tokenizer_id", "license_id"):
            _identifier(getattr(self, name), name)
        for name in ("revision", "tokenizer_revision"):
            value = getattr(self, name)
            if not 7 <= len(value) <= 64 or any(
                character not in "0123456789abcdef" for character in value
            ):
                raise ValueError(f"{name} must be an immutable lowercase revision")
        _sha256(self.files_manifest_sha256, "files_manifest_sha256")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class AdapterTrainingRecipe:
    recipe_id: str
    method: AdapterTrainingMethod
    rank: int
    alpha: int
    dropout: float
    target_modules: tuple[str, ...]
    base_weight_bits: int
    quantization_type: str | None
    double_quantization: bool
    compute_dtype: TrainingComputeDtype
    maximum_sequence_tokens: int
    epochs: float
    maximum_steps: int
    per_device_batch_size: int
    gradient_accumulation_steps: int
    learning_rate: float
    seed: int
    contract_version: str = FACTORY_TRAINING_APPROVAL_VERSION

    def __post_init__(self) -> None:
        _identifier(self.recipe_id, "recipe_id")
        if not isinstance(self.method, AdapterTrainingMethod):
            raise ValueError("training method is invalid")
        if not 1 <= self.rank <= 256 or not self.rank <= self.alpha <= 1_024:
            raise ValueError("LoRA rank or alpha is outside the approved bound")
        if not math.isfinite(self.dropout) or not 0 <= self.dropout <= 0.5:
            raise ValueError("LoRA dropout is invalid")
        if not self.target_modules or len(set(self.target_modules)) != len(self.target_modules):
            raise ValueError("LoRA target modules must be nonempty and unique")
        for value in self.target_modules:
            _identifier(value, "target_module")
        if self.method is AdapterTrainingMethod.QLORA:
            if (
                self.base_weight_bits != 4
                or self.quantization_type != "nf4"
                or not self.double_quantization
            ):
                raise ValueError("QLoRA requires 4-bit NF4 double quantization")
        elif self.base_weight_bits not in {16, 32} or self.quantization_type is not None:
            raise ValueError("LoRA base precision is invalid")
        if not isinstance(self.compute_dtype, TrainingComputeDtype):
            raise ValueError("training compute dtype is invalid")
        if not 128 <= self.maximum_sequence_tokens <= 32_768:
            raise ValueError("training sequence bound is invalid")
        if not math.isfinite(self.epochs) or not 0 < self.epochs <= 20:
            raise ValueError("training epoch bound is invalid")
        if not 1 <= self.maximum_steps <= 1_000_000:
            raise ValueError("training step bound is invalid")
        if not 1 <= self.per_device_batch_size <= 128:
            raise ValueError("training batch size is invalid")
        if not 1 <= self.gradient_accumulation_steps <= 1_024:
            raise ValueError("gradient accumulation bound is invalid")
        if not math.isfinite(self.learning_rate) or not 0 < self.learning_rate <= 0.1:
            raise ValueError("learning rate is invalid")
        if self.seed < 0 or self.seed > 2**63 - 1:
            raise ValueError("training seed is invalid")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class TrainingResourceBudget:
    budget_id: str
    maximum_cpu_cores: int
    maximum_ram_bytes: int
    maximum_vram_bytes: int
    maximum_disk_bytes: int
    maximum_temperature_celsius: int
    maximum_energy_joules: int
    cgroup_policy_id: str
    contract_version: str = FACTORY_TRAINING_APPROVAL_VERSION

    def __post_init__(self) -> None:
        _identifier(self.budget_id, "budget_id")
        _identifier(self.cgroup_policy_id, "cgroup_policy_id")
        if not 1 <= self.maximum_cpu_cores <= 512:
            raise ValueError("training CPU budget is invalid")
        for name in ("maximum_ram_bytes", "maximum_vram_bytes", "maximum_disk_bytes"):
            if getattr(self, name) < 256 * 1024 * 1024:
                raise ValueError(f"{name} is below the minimum explicit bound")
        if not 40 <= self.maximum_temperature_celsius <= 95:
            raise ValueError("training thermal budget is invalid")
        if self.maximum_energy_joules < 1:
            raise ValueError("training energy budget is invalid")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class FactoryTrainingApproval:
    approval_id: str
    proposal_id: str
    capability_id: str
    sealed_dataset_id: str
    sealed_dataset_sha256: str
    approved_dataset_license_ids: tuple[str, ...]
    approved_dataset_sensitivities: tuple[str, ...]
    base_model: ApprovedBaseModel
    recipe: AdapterTrainingRecipe
    resources: TrainingResourceBudget
    environment_sha256: str
    maximum_wall_seconds: int
    maximum_checkpoint_bytes: int
    maximum_output_bytes: int
    one_use_job_id: str
    issued_at: datetime
    expires_at: datetime
    confirmed: bool
    network_allowed: bool = False
    revision: int = 1
    training_authorized: bool = True
    contract_version: str = FACTORY_TRAINING_APPROVAL_VERSION

    def __post_init__(self) -> None:
        for name in (
            "approval_id", "proposal_id", "capability_id", "sealed_dataset_id",
            "one_use_job_id",
        ):
            _identifier(getattr(self, name), name)
        _sha256(self.sealed_dataset_sha256, "sealed_dataset_sha256")
        for name in (
            "approved_dataset_license_ids", "approved_dataset_sensitivities",
        ):
            values = getattr(self, name)
            if not values or values != tuple(sorted(set(values))):
                raise ValueError(f"{name} must be sorted, nonempty, and unique")
            for value in values:
                _identifier(value, name)
        _sha256(self.environment_sha256, "environment_sha256")
        if not 60 <= self.maximum_wall_seconds <= 7 * 24 * 60 * 60:
            raise ValueError("training wall-time approval is invalid")
        for name in ("maximum_checkpoint_bytes", "maximum_output_bytes"):
            if not 1 <= getattr(self, name) <= self.resources.maximum_disk_bytes:
                raise ValueError(f"{name} exceeds the approved disk budget")
        _aware(self.issued_at, "issued_at")
        _aware(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("training approval expiry must follow issuance")
        if not self.confirmed or not self.training_authorized:
            raise ValueError("training approval requires explicit authority")
        if self.network_allowed:
            raise ValueError("initial training workers must be network denied")
        if self.revision < 1:
            raise ValueError("training approval revision is invalid")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class TrainingApprovalConsumption:
    receipt_id: str
    approval_id: str
    job_id: str
    approval_revision: int
    consumed_at: datetime
    contract_version: str = FACTORY_TRAINING_APPROVAL_VERSION

    def __post_init__(self) -> None:
        for name in ("receipt_id", "approval_id", "job_id"):
            _identifier(getattr(self, name), name)
        if self.approval_revision < 1:
            raise ValueError("consumed approval revision is invalid")
        _aware(self.consumed_at, "consumed_at")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class TrainingApprovalRevocation:
    receipt_id: str
    approval_id: str
    previous_revision: int
    current_revision: int
    reason_code: str
    revoked_at: datetime
    contract_version: str = FACTORY_TRAINING_APPROVAL_VERSION

    def __post_init__(self) -> None:
        for name in ("receipt_id", "approval_id", "reason_code"):
            _identifier(getattr(self, name), name)
        if self.previous_revision < 1 or self.current_revision != self.previous_revision + 1:
            raise ValueError("training revocation revision is invalid")
        _aware(self.revoked_at, "revoked_at")
        _version(self.contract_version)


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
    if value != FACTORY_TRAINING_APPROVAL_VERSION:
        raise ValueError("unsupported factory training approval version")
