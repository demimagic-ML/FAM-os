"""Digest-pinned runtime conversion contracts after a promotable decision."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


FACTORY_CONVERSION_VERSION = "fam.factory.conversion/v1alpha1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


class ConversionOutputType(StrEnum):
    F16 = "f16"
    BF16 = "bf16"
    Q8_0 = "q8_0"


class ConversionStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class FactoryConversionEnvironment:
    environment_id: str
    llama_cpp_revision: str
    convert_hf_script_sha256: str
    convert_lora_script_sha256: str
    wheelhouse_manifest_sha256: str
    python_executable_sha256: str
    package_versions: tuple[tuple[str, str], ...]
    ollama_version: str
    manifest_sha256: str
    observed_at: datetime
    contract_version: str = FACTORY_CONVERSION_VERSION

    def __post_init__(self) -> None:
        _identifier(self.environment_id)
        if len(self.llama_cpp_revision) != 40:
            raise ValueError("llama.cpp revision must be an immutable Git commit")
        for value in (
            self.convert_hf_script_sha256, self.convert_lora_script_sha256,
            self.wheelhouse_manifest_sha256, self.python_executable_sha256,
            self.manifest_sha256,
        ):
            _sha(value)
        if not self.package_versions or self.package_versions != tuple(
            sorted(set(self.package_versions))
        ):
            raise ValueError("conversion packages must be sorted and unique")
        if any(not name or not version for name, version in self.package_versions):
            raise ValueError("conversion package versions are invalid")
        if not self.ollama_version.strip():
            raise ValueError("conversion runtime version is unavailable")
        _aware(self.observed_at)
        if self.manifest_sha256 != conversion_environment_digest(self):
            raise ValueError("conversion environment digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class FactoryConversionApproval:
    approval_id: str
    evaluation_id: str
    comparison_decision_id: str
    comparison_decision_sha256: str
    adapter_sha256: str
    base_model_sha256: str
    environment_sha256: str
    base_output_type: ConversionOutputType
    adapter_output_type: ConversionOutputType
    runtime_model_ref: str
    maximum_output_bytes: int
    maximum_wall_seconds: int
    maximum_ram_bytes: int
    maximum_cpu_cores: int
    one_use_conversion_id: str
    issued_at: datetime
    expires_at: datetime
    revision: int
    active: bool
    approval_sha256: str
    contract_version: str = FACTORY_CONVERSION_VERSION

    def __post_init__(self) -> None:
        for value in (
            self.approval_id, self.evaluation_id, self.comparison_decision_id,
            self.runtime_model_ref, self.one_use_conversion_id,
        ):
            _identifier(value)
        for value in (
            self.comparison_decision_sha256, self.adapter_sha256,
            self.base_model_sha256, self.environment_sha256, self.approval_sha256,
        ):
            _sha(value)
        if self.base_output_type not in (
            ConversionOutputType.F16, ConversionOutputType.BF16,
            ConversionOutputType.Q8_0,
        ) or self.adapter_output_type not in (
            ConversionOutputType.F16, ConversionOutputType.BF16,
        ):
            raise ValueError("conversion output type is invalid")
        if (
            self.maximum_output_bytes < 1
            or self.maximum_ram_bytes < 256 * 1024**2
            or not 1 <= self.maximum_cpu_cores <= 1024
            or not 60 <= self.maximum_wall_seconds <= 24 * 60 * 60
            or self.revision < 1
            or not self.active
        ):
            raise ValueError("conversion approval limits are invalid")
        _aware(self.issued_at)
        _aware(self.expires_at)
        if self.expires_at <= self.issued_at:
            raise ValueError("conversion approval expiry is invalid")
        if self.approval_sha256 != conversion_approval_digest(self):
            raise ValueError("conversion approval digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class FactoryConversionReceipt:
    receipt_id: str
    approval_id: str
    conversion_id: str
    comparison_decision_sha256: str
    environment_sha256: str
    status: ConversionStatus
    reason_code: str
    base_gguf_sha256: str | None
    base_gguf_bytes: int
    adapter_gguf_sha256: str | None
    adapter_gguf_bytes: int
    modelfile_sha256: str | None
    runtime_model_ref: str | None
    network_denied: bool
    started_at: datetime
    finished_at: datetime
    receipt_sha256: str
    contract_version: str = FACTORY_CONVERSION_VERSION

    def __post_init__(self) -> None:
        for identifier in (self.receipt_id, self.approval_id, self.conversion_id):
            _identifier(identifier)
        _sha(self.comparison_decision_sha256)
        _sha(self.environment_sha256)
        _sha(self.receipt_sha256)
        _identifier(self.reason_code)
        for byte_count in (self.base_gguf_bytes, self.adapter_gguf_bytes):
            if byte_count < 0:
                raise ValueError("conversion output size cannot be negative")
        completed = self.status is ConversionStatus.COMPLETED
        outputs = (
            self.base_gguf_sha256, self.adapter_gguf_sha256,
            self.modelfile_sha256, self.runtime_model_ref,
        )
        if completed:
            if any(value is None for value in outputs) or not self.network_denied:
                raise ValueError("completed conversion lacks isolated outputs")
            if self.base_gguf_bytes < 1 or self.adapter_gguf_bytes < 1:
                raise ValueError("completed conversion outputs are empty")
            for output_digest in outputs[:3]:
                _sha(output_digest)
            _identifier(self.runtime_model_ref)
        elif any(value is not None for value in outputs) or (
            self.base_gguf_bytes or self.adapter_gguf_bytes
        ):
            raise ValueError("failed conversion cannot claim outputs")
        _aware(self.started_at)
        _aware(self.finished_at)
        if self.finished_at < self.started_at:
            raise ValueError("conversion time range is invalid")
        if self.receipt_sha256 != conversion_receipt_digest(self):
            raise ValueError("conversion receipt digest does not match")
        _version(self.contract_version)


def build_conversion_environment(**values: object) -> FactoryConversionEnvironment:
    document = dict(values)
    document["manifest_sha256"] = _digest(_without(
        document, "contract_version", "observed_at",
    ))
    return FactoryConversionEnvironment(**document)  # type: ignore[arg-type]


def build_conversion_approval(**values: object) -> FactoryConversionApproval:
    document = dict(values)
    document.setdefault("revision", 1)
    document.setdefault("active", True)
    document["approval_sha256"] = _digest(_without(
        document, "approval_sha256", "contract_version",
    ))
    return FactoryConversionApproval(**document)  # type: ignore[arg-type]


def build_conversion_receipt(**values: object) -> FactoryConversionReceipt:
    document = dict(values)
    document["receipt_sha256"] = _digest(_without(
        document, "receipt_sha256", "contract_version",
    ))
    return FactoryConversionReceipt(**document)  # type: ignore[arg-type]


def conversion_environment_digest(value: FactoryConversionEnvironment) -> str:
    return _digest(_without(
        dict(_fields(value)), "manifest_sha256", "contract_version", "observed_at",
    ))


def conversion_approval_digest(value: FactoryConversionApproval) -> str:
    return _digest(_without(
        dict(_fields(value)), "approval_sha256", "contract_version",
    ))


def conversion_receipt_digest(value: FactoryConversionReceipt) -> str:
    return _digest(_without(
        dict(_fields(value)), "receipt_sha256", "contract_version",
    ))


def _fields(value: object) -> tuple[tuple[str, object], ...]:
    return tuple((name, getattr(value, name)) for name in value.__dataclass_fields__)  # type: ignore[attr-defined]


def _without(values: dict[str, object], *names: str) -> dict[str, object]:
    return {name: _canonical(value) for name, value in values.items() if name not in names}


def _canonical(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return tuple(_canonical(item) for item in value)
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        _canonical(value), sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def _identifier(value: str | None) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError("factory conversion identifier is invalid")


def _sha(value: str | None) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError("factory conversion digest must be lowercase SHA-256")


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("factory conversion timestamp must be timezone-aware")


def _version(value: str) -> None:
    if value != FACTORY_CONVERSION_VERSION:
        raise ValueError("unsupported factory conversion contract version")
