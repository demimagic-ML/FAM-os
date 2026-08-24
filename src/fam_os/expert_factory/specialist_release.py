"""Audit lineage and disabled-install receipt for a promoted specialist."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime

from fam_os.expert_factory.conversion import ConversionOutputType


FACTORY_SPECIALIST_RELEASE_VERSION = "fam.factory.specialist-release/v1alpha1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


@dataclass(frozen=True, slots=True)
class FactorySpecialistReleaseLineage:
    release_id: str
    package_id: str
    package_version: str
    expert_id: str
    training_capability_id: str
    declared_capabilities: tuple[str, ...]
    required_verifier_ids: tuple[str, ...]
    conversion_receipt_id: str
    conversion_receipt_sha256: str
    conversion_environment_sha256: str
    comparison_decision_id: str
    comparison_decision_sha256: str
    training_receipt_id: str
    sealed_dataset_id: str
    sealed_dataset_sha256: str
    base_model_id: str
    base_model_revision: str
    base_model_files_sha256: str
    adapter_sha256: str
    base_gguf_sha256: str
    adapter_gguf_sha256: str
    modelfile_sha256: str
    tokenizer_sha256: str
    chat_template_sha256: str
    merge_policy: str
    base_output_type: ConversionOutputType
    adapter_output_type: ConversionOutputType
    runtime_model_ref: str
    license_id: str
    estimated_resident_bytes: int
    storage_bytes: int
    max_context_tokens: int
    minimum_system_memory_bytes: int
    minimum_accelerator_memory_bytes: int
    accelerator_optional: bool
    supported_architectures: tuple[str, ...]
    created_at: datetime
    lineage_sha256: str
    contract_version: str = FACTORY_SPECIALIST_RELEASE_VERSION

    def __post_init__(self) -> None:
        for value in (
            self.release_id, self.package_id, self.package_version,
            self.expert_id, self.training_capability_id,
            self.conversion_receipt_id, self.comparison_decision_id,
            self.training_receipt_id, self.sealed_dataset_id,
            self.base_model_id, self.base_model_revision, self.merge_policy,
            self.runtime_model_ref, self.license_id,
        ):
            _identifier(value)
        _unique(self.declared_capabilities, "declared capabilities")
        _unique(
            self.required_verifier_ids, "required verifiers", allow_empty=True,
        )
        _unique(self.supported_architectures, "architectures")
        for value in (
            self.conversion_receipt_sha256,
            self.conversion_environment_sha256,
            self.comparison_decision_sha256, self.sealed_dataset_sha256,
            self.base_model_files_sha256, self.adapter_sha256,
            self.base_gguf_sha256, self.adapter_gguf_sha256,
            self.modelfile_sha256, self.tokenizer_sha256,
            self.chat_template_sha256, self.lineage_sha256,
        ):
            _sha(value)
        if self.merge_policy != "runtime_lora_adapter":
            raise ValueError("specialist merge policy is unsupported")
        if self.adapter_output_type not in (
            ConversionOutputType.F16, ConversionOutputType.BF16,
        ):
            raise ValueError("specialist adapter output type is invalid")
        for resource_value in (
            self.estimated_resident_bytes, self.storage_bytes,
            self.max_context_tokens, self.minimum_system_memory_bytes,
        ):
            if resource_value < 1:
                raise ValueError("specialist resource values must be positive")
        if self.minimum_accelerator_memory_bytes < 0:
            raise ValueError("specialist accelerator memory cannot be negative")
        _aware(self.created_at)
        if self.lineage_sha256 != specialist_release_lineage_digest(self):
            raise ValueError("specialist release lineage digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class FactorySpecialistPackageReceipt:
    receipt_id: str
    release_id: str
    package_id: str
    package_version: str
    lineage_sha256: str
    artifact_sha256: str
    expert_manifest_sha256: str
    runtime_binding_sha256: str
    signature_sha256: str
    signature_key_id: str
    validation_policy_id: str
    compatibility_sha256: str
    artifact_locator: str
    lifecycle_revision: int
    installed_disabled: bool
    installed_at: datetime
    receipt_sha256: str
    contract_version: str = FACTORY_SPECIALIST_RELEASE_VERSION

    def __post_init__(self) -> None:
        for value in (
            self.receipt_id, self.release_id, self.package_id,
            self.package_version, self.signature_key_id,
            self.validation_policy_id, self.artifact_locator,
        ):
            _identifier(value)
        for value in (
            self.lineage_sha256, self.artifact_sha256,
            self.expert_manifest_sha256, self.runtime_binding_sha256,
            self.signature_sha256, self.compatibility_sha256,
            self.receipt_sha256,
        ):
            _sha(value)
        if self.lifecycle_revision < 1 or not self.installed_disabled:
            raise ValueError("specialist package must be installed disabled")
        _aware(self.installed_at)
        if self.receipt_sha256 != specialist_package_receipt_digest(self):
            raise ValueError("specialist package receipt digest does not match")
        _version(self.contract_version)


def build_specialist_release_lineage(
    **values: object,
) -> FactorySpecialistReleaseLineage:
    document = dict(values)
    document["lineage_sha256"] = _digest(document)
    return FactorySpecialistReleaseLineage(**document)  # type: ignore[arg-type]


def build_specialist_package_receipt(
    **values: object,
) -> FactorySpecialistPackageReceipt:
    document = dict(values)
    document["receipt_sha256"] = _digest(document)
    return FactorySpecialistPackageReceipt(**document)  # type: ignore[arg-type]


def specialist_release_lineage_digest(
    value: FactorySpecialistReleaseLineage,
) -> str:
    return _digest(_without(_fields(value), "lineage_sha256", "contract_version"))


def specialist_package_receipt_digest(
    value: FactorySpecialistPackageReceipt,
) -> str:
    return _digest(_without(_fields(value), "receipt_sha256", "contract_version"))


def _fields(value: object) -> dict[str, object]:
    return {
        name: getattr(value, name)
        for name in value.__dataclass_fields__  # type: ignore[attr-defined]
    }


def _without(values: dict[str, object], *names: str) -> dict[str, object]:
    return {name: item for name, item in values.items() if name not in names}


def _canonical(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ConversionOutputType):
        return value.value
    if isinstance(value, tuple):
        return tuple(_canonical(item) for item in value)
    if isinstance(value, dict):
        return {name: _canonical(item) for name, item in value.items()}
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        _canonical(value), sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def _identifier(value: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError("specialist release identifier is invalid")


def _sha(value: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError("specialist release digest must be lowercase SHA-256")


def _unique(values: tuple[str, ...], name: str, allow_empty: bool = False) -> None:
    if (not allow_empty and not values) or len(set(values)) != len(values) or any(
        not value.strip() for value in values
    ):
        raise ValueError(f"specialist {name} must be unique nonempty values")


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("specialist release timestamp must be timezone-aware")


def _version(value: str) -> None:
    if value != FACTORY_SPECIALIST_RELEASE_VERSION:
        raise ValueError("unsupported specialist release contract version")
