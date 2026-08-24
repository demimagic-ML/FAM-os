"""Immutable held-out comparison contracts for real specialist promotion."""

from __future__ import annotations

import hashlib
import json
import math
import re
import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


FACTORY_EVALUATION_VERSION = "fam.factory.evaluation/v1alpha1"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


class EvaluationCaseKind(StrEnum):
    QUALITY = "quality"
    SAFETY = "safety"
    POLICY = "policy"
    UNRELATED = "unrelated"


@dataclass(frozen=True, slots=True)
class FactoryEvaluationPolicy:
    policy_id: str
    capability_id: str
    minimum_quality_cases: int
    minimum_quality_ppm: int
    minimum_improvement_ppm: int
    confidence_z_ppm: int
    maximum_unrelated_regression_ppm: int
    maximum_p95_latency_microseconds: int
    maximum_latency_regression_ppm: int
    maximum_peak_ram_bytes: int
    maximum_peak_vram_bytes: int
    maximum_energy_joules: int
    maximum_resource_regression_ppm: int
    maximum_adapter_bytes: int
    maximum_cold_start_microseconds: int
    require_scheduler_compatibility: bool
    policy_sha256: str
    contract_version: str = FACTORY_EVALUATION_VERSION

    def __post_init__(self) -> None:
        _identifier(self.policy_id, "policy_id")
        _identifier(self.capability_id, "capability_id")
        if self.minimum_quality_cases < 30:
            raise ValueError("evaluation requires at least 30 quality cases")
        for name in (
            "minimum_quality_ppm", "minimum_improvement_ppm",
            "maximum_unrelated_regression_ppm", "maximum_latency_regression_ppm",
            "maximum_resource_regression_ppm",
        ):
            if not 0 <= getattr(self, name) <= 1_000_000:
                raise ValueError("evaluation ratio threshold is invalid")
        if not 1_000_000 <= self.confidence_z_ppm <= 4_000_000:
            raise ValueError("evaluation confidence threshold is invalid")
        for name in (
            "maximum_p95_latency_microseconds", "maximum_peak_ram_bytes",
            "maximum_peak_vram_bytes", "maximum_energy_joules",
            "maximum_adapter_bytes", "maximum_cold_start_microseconds",
        ):
            if getattr(self, name) < 1:
                raise ValueError("evaluation resource threshold is invalid")
        _sha(self.policy_sha256, "policy_sha256")
        if self.policy_sha256 != evaluation_policy_digest(self):
            raise ValueError("evaluation policy digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class FactoryEvaluationApproval:
    approval_id: str
    proposal_id: str
    capability_id: str
    training_receipt_id: str
    adapter_sha256: str
    adapter_config_sha256: str
    sealed_dataset_id: str
    sealed_dataset_sha256: str
    held_out_blob_id: str
    held_out_blob_sha256: str
    incumbent_expert_id: str
    incumbent_artifact_sha256: str
    suite_sha256: str
    evaluator_environment_sha256: str
    evaluator_script_sha256: str
    policy: FactoryEvaluationPolicy
    one_use_evaluation_id: str
    issued_at: datetime
    expires_at: datetime
    revision: int
    active: bool
    approval_sha256: str
    contract_version: str = FACTORY_EVALUATION_VERSION

    def __post_init__(self) -> None:
        for name in (
            "approval_id", "proposal_id", "capability_id", "training_receipt_id",
            "sealed_dataset_id", "held_out_blob_id", "incumbent_expert_id",
            "one_use_evaluation_id",
        ):
            _identifier(getattr(self, name), name)
        for name in (
            "adapter_sha256", "adapter_config_sha256", "sealed_dataset_sha256",
            "held_out_blob_sha256", "incumbent_artifact_sha256", "suite_sha256",
            "evaluator_environment_sha256", "evaluator_script_sha256",
            "approval_sha256",
        ):
            _sha(getattr(self, name), name)
        if self.policy.capability_id != self.capability_id:
            raise ValueError("evaluation policy capability does not match approval")
        _aware(self.issued_at)
        _aware(self.expires_at)
        if self.expires_at <= self.issued_at or self.revision < 1 or not self.active:
            raise ValueError("evaluation approval lifecycle is invalid")
        if self.approval_sha256 != evaluation_approval_digest(self):
            raise ValueError("evaluation approval digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class HeldOutAccessReceipt:
    receipt_id: str
    approval_id: str
    evaluation_id: str
    dataset_id: str
    held_out_blob_id: str
    held_out_blob_sha256: str
    evaluator_environment_sha256: str
    plaintext_bytes: int
    plaintext_discarded: bool
    accessed_at: datetime
    receipt_sha256: str
    contract_version: str = FACTORY_EVALUATION_VERSION

    def __post_init__(self) -> None:
        for name in (
            "receipt_id", "approval_id", "evaluation_id", "dataset_id",
            "held_out_blob_id",
        ):
            _identifier(getattr(self, name), name)
        _sha(self.held_out_blob_sha256, "held_out_blob_sha256")
        _sha(self.evaluator_environment_sha256, "evaluator_environment_sha256")
        _sha(self.receipt_sha256, "receipt_sha256")
        if self.plaintext_bytes < 1 or not self.plaintext_discarded:
            raise ValueError("held-out access disposition is invalid")
        _aware(self.accessed_at)
        if self.receipt_sha256 != held_out_access_digest(self):
            raise ValueError("held-out access receipt digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class PairedEvaluationMeasurement:
    measurement_id: str
    evaluation_id: str
    case_id: str
    kind: EvaluationCaseKind
    requirement_id: str
    input_sha256: str
    expected_sha256: str
    baseline_output_sha256: str
    candidate_output_sha256: str
    baseline_passed: bool
    candidate_passed: bool
    baseline_latency_microseconds: int
    candidate_latency_microseconds: int
    baseline_peak_ram_bytes: int
    candidate_peak_ram_bytes: int
    baseline_peak_vram_bytes: int
    candidate_peak_vram_bytes: int
    baseline_energy_millijoules: int
    candidate_energy_millijoules: int
    measured_at: datetime
    measurement_sha256: str
    contract_version: str = FACTORY_EVALUATION_VERSION

    def __post_init__(self) -> None:
        for name in ("measurement_id", "evaluation_id", "case_id", "requirement_id"):
            _identifier(getattr(self, name), name)
        if not isinstance(self.kind, EvaluationCaseKind):
            raise ValueError("evaluation case kind is invalid")
        for name in (
            "input_sha256", "expected_sha256", "baseline_output_sha256",
            "candidate_output_sha256", "measurement_sha256",
        ):
            _sha(getattr(self, name), name)
        for name in (
            "baseline_latency_microseconds", "candidate_latency_microseconds",
            "baseline_peak_ram_bytes", "candidate_peak_ram_bytes",
            "baseline_peak_vram_bytes", "candidate_peak_vram_bytes",
            "baseline_energy_millijoules", "candidate_energy_millijoules",
        ):
            if getattr(self, name) < 0:
                raise ValueError("evaluation measurement cannot be negative")
        _aware(self.measured_at)
        if self.measurement_sha256 != paired_measurement_digest(self):
            raise ValueError("evaluation measurement digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ExpertEvaluationReport:
    report_id: str
    approval_id: str
    evaluation_id: str
    policy_sha256: str
    evaluator_environment_sha256: str
    evaluator_script_sha256: str
    held_out_access_receipt_sha256: str
    network_denied: bool
    measurement_manifest_sha256: str
    case_count: int
    quality_case_count: int
    baseline_quality_passes: int
    candidate_quality_passes: int
    baseline_quality_ppm: int
    candidate_quality_ppm: int
    baseline_quality_lower_ppm: int
    baseline_quality_upper_ppm: int
    candidate_quality_lower_ppm: int
    candidate_quality_upper_ppm: int
    baseline_safety_failures: int
    candidate_safety_failures: int
    baseline_policy_failures: int
    candidate_policy_failures: int
    baseline_unrelated_quality_ppm: int
    candidate_unrelated_quality_ppm: int
    baseline_p95_latency_microseconds: int
    candidate_p95_latency_microseconds: int
    baseline_peak_ram_bytes: int
    candidate_peak_ram_bytes: int
    baseline_peak_vram_bytes: int
    candidate_peak_vram_bytes: int
    baseline_energy_joules: int
    candidate_energy_joules: int
    candidate_adapter_bytes: int
    candidate_cold_start_microseconds: int
    scheduler_compatible: bool
    started_at: datetime
    finished_at: datetime
    report_sha256: str
    contract_version: str = FACTORY_EVALUATION_VERSION

    def __post_init__(self) -> None:
        for name in ("report_id", "approval_id", "evaluation_id"):
            _identifier(getattr(self, name), name)
        for name in (
            "policy_sha256", "evaluator_environment_sha256",
            "evaluator_script_sha256", "held_out_access_receipt_sha256",
            "measurement_manifest_sha256", "report_sha256",
        ):
            _sha(getattr(self, name), name)
        if not self.network_denied:
            raise ValueError("evaluation report requires network denial")
        if self.case_count < 1 or not 1 <= self.quality_case_count <= self.case_count:
            raise ValueError("evaluation report case counts are invalid")
        for name in (
            "baseline_quality_ppm", "candidate_quality_ppm",
            "baseline_quality_lower_ppm", "baseline_quality_upper_ppm",
            "candidate_quality_lower_ppm", "candidate_quality_upper_ppm",
            "baseline_unrelated_quality_ppm", "candidate_unrelated_quality_ppm",
        ):
            if not 0 <= getattr(self, name) <= 1_000_000:
                raise ValueError("evaluation quality ratio is invalid")
        for name in (
            "baseline_quality_passes", "candidate_quality_passes",
            "baseline_safety_failures", "candidate_safety_failures",
            "baseline_policy_failures", "candidate_policy_failures",
            "baseline_p95_latency_microseconds", "candidate_p95_latency_microseconds",
            "baseline_peak_ram_bytes", "candidate_peak_ram_bytes",
            "baseline_peak_vram_bytes", "candidate_peak_vram_bytes",
            "baseline_energy_joules", "candidate_energy_joules",
            "candidate_adapter_bytes", "candidate_cold_start_microseconds",
        ):
            if getattr(self, name) < 0:
                raise ValueError("evaluation report metric cannot be negative")
        _aware(self.started_at)
        _aware(self.finished_at)
        if self.finished_at < self.started_at:
            raise ValueError("evaluation report time range is invalid")
        if self.report_sha256 != evaluation_report_digest(self):
            raise ValueError("evaluation report digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ExpertComparisonDecision:
    decision_id: str
    approval_id: str
    evaluation_id: str
    report_sha256: str
    promotable: bool
    reason_codes: tuple[str, ...]
    decided_at: datetime
    signer_key_id: str
    signer_public_key_base64: str
    decision_sha256: str
    signature_base64: str
    contract_version: str = FACTORY_EVALUATION_VERSION

    def __post_init__(self) -> None:
        for name in ("decision_id", "approval_id", "evaluation_id", "signer_key_id"):
            _identifier(getattr(self, name), name)
        _sha(self.report_sha256, "report_sha256")
        _sha(self.decision_sha256, "decision_sha256")
        if self.promotable == bool(self.reason_codes):
            raise ValueError("evaluation decision reasons are inconsistent")
        if self.reason_codes != tuple(sorted(set(self.reason_codes))):
            raise ValueError("evaluation decision reasons must be sorted and unique")
        _aware(self.decided_at)
        if self.decision_sha256 != comparison_decision_digest(self):
            raise ValueError("evaluation decision digest does not match")
        _verify_decision_signature(self)
        _version(self.contract_version)


def build_evaluation_policy(**values: object) -> FactoryEvaluationPolicy:
    document = dict(values)
    document["policy_sha256"] = _digest(document)
    return FactoryEvaluationPolicy(**document)  # type: ignore[arg-type]


def build_evaluation_approval(**values: object) -> FactoryEvaluationApproval:
    document = dict(values)
    document.setdefault("revision", 1)
    document.setdefault("active", True)
    document["approval_sha256"] = _digest(_approval_document(document))
    return FactoryEvaluationApproval(**document)  # type: ignore[arg-type]


def build_held_out_access_receipt(**values: object) -> HeldOutAccessReceipt:
    document = dict(values)
    document["receipt_sha256"] = _digest(_access_document(document))
    return HeldOutAccessReceipt(**document)  # type: ignore[arg-type]


def build_paired_measurement(**values: object) -> PairedEvaluationMeasurement:
    document = dict(values)
    document["measurement_sha256"] = _digest(_measurement_document(document))
    return PairedEvaluationMeasurement(**document)  # type: ignore[arg-type]


def build_evaluation_report(
    *, report_id: str, approval_id: str, evaluation_id: str,
    policy: FactoryEvaluationPolicy,
    evaluator_environment_sha256: str, evaluator_script_sha256: str,
    held_out_access_receipt_sha256: str, network_denied: bool,
    measurements: tuple[PairedEvaluationMeasurement, ...],
    candidate_adapter_bytes: int, candidate_cold_start_microseconds: int,
    scheduler_compatible: bool, started_at: datetime, finished_at: datetime,
) -> ExpertEvaluationReport:
    if not measurements or len({item.case_id for item in measurements}) != len(measurements):
        raise ValueError("evaluation measurements must be nonempty and case-unique")
    if any(item.evaluation_id != evaluation_id for item in measurements):
        raise ValueError("evaluation measurement identity does not match")
    quality = tuple(item for item in measurements if item.kind is EvaluationCaseKind.QUALITY)
    unrelated = tuple(item for item in measurements if item.kind is EvaluationCaseKind.UNRELATED)
    baseline_quality = sum(item.baseline_passed for item in quality)
    candidate_quality = sum(item.candidate_passed for item in quality)
    baseline_bounds = _wilson_bounds(baseline_quality, len(quality), policy.confidence_z_ppm)
    candidate_bounds = _wilson_bounds(candidate_quality, len(quality), policy.confidence_z_ppm)
    values: dict[str, object] = {
        "report_id": report_id, "approval_id": approval_id,
        "evaluation_id": evaluation_id, "policy_sha256": policy.policy_sha256,
        "evaluator_environment_sha256": evaluator_environment_sha256,
        "evaluator_script_sha256": evaluator_script_sha256,
        "held_out_access_receipt_sha256": held_out_access_receipt_sha256,
        "network_denied": network_denied,
        "measurement_manifest_sha256": _digest(tuple(
            item.measurement_sha256 for item in measurements
        )),
        "case_count": len(measurements), "quality_case_count": len(quality),
        "baseline_quality_passes": baseline_quality,
        "candidate_quality_passes": candidate_quality,
        "baseline_quality_ppm": _rate(baseline_quality, len(quality)),
        "candidate_quality_ppm": _rate(candidate_quality, len(quality)),
        "baseline_quality_lower_ppm": baseline_bounds[0],
        "baseline_quality_upper_ppm": baseline_bounds[1],
        "candidate_quality_lower_ppm": candidate_bounds[0],
        "candidate_quality_upper_ppm": candidate_bounds[1],
        "baseline_safety_failures": _failures(measurements, EvaluationCaseKind.SAFETY, False),
        "candidate_safety_failures": _failures(measurements, EvaluationCaseKind.SAFETY, True),
        "baseline_policy_failures": _failures(measurements, EvaluationCaseKind.POLICY, False),
        "candidate_policy_failures": _failures(measurements, EvaluationCaseKind.POLICY, True),
        "baseline_unrelated_quality_ppm": _passed_rate(unrelated, False),
        "candidate_unrelated_quality_ppm": _passed_rate(unrelated, True),
        "baseline_p95_latency_microseconds": _percentile(
            tuple(item.baseline_latency_microseconds for item in measurements), 95,
        ),
        "candidate_p95_latency_microseconds": _percentile(
            tuple(item.candidate_latency_microseconds for item in measurements), 95,
        ),
        "baseline_peak_ram_bytes": max(item.baseline_peak_ram_bytes for item in measurements),
        "candidate_peak_ram_bytes": max(item.candidate_peak_ram_bytes for item in measurements),
        "baseline_peak_vram_bytes": max(item.baseline_peak_vram_bytes for item in measurements),
        "candidate_peak_vram_bytes": max(item.candidate_peak_vram_bytes for item in measurements),
        "baseline_energy_joules": math.ceil(sum(
            item.baseline_energy_millijoules for item in measurements
        ) / 1000),
        "candidate_energy_joules": math.ceil(sum(
            item.candidate_energy_millijoules for item in measurements
        ) / 1000),
        "candidate_adapter_bytes": candidate_adapter_bytes,
        "candidate_cold_start_microseconds": candidate_cold_start_microseconds,
        "scheduler_compatible": scheduler_compatible,
        "started_at": started_at, "finished_at": finished_at,
    }
    values["report_sha256"] = _digest(_report_document(values))
    return ExpertEvaluationReport(**values)  # type: ignore[arg-type]


def decide_comparison(
    *, decision_id: str, approval: FactoryEvaluationApproval,
    report: ExpertEvaluationReport, decided_at: datetime,
    signer_key_id: str, signing_key: Ed25519PrivateKey,
) -> ExpertComparisonDecision:
    if report.approval_id != approval.approval_id or (
        report.policy_sha256 != approval.policy.policy_sha256
    ) or report.evaluator_environment_sha256 != (
        approval.evaluator_environment_sha256
    ) or report.evaluator_script_sha256 != (
        approval.evaluator_script_sha256
    ):
        raise ValueError("evaluation report does not bind its approval")
    policy = approval.policy
    reasons = []
    if report.quality_case_count < policy.minimum_quality_cases:
        reasons.append("quality.sample_count_insufficient")
    if report.candidate_quality_lower_ppm < policy.minimum_quality_ppm:
        reasons.append("quality.minimum_not_met")
    if (
        report.candidate_quality_lower_ppm - report.baseline_quality_upper_ppm
        < policy.minimum_improvement_ppm
    ):
        reasons.append("quality.confident_improvement_not_met")
    if report.candidate_safety_failures:
        reasons.append("safety.failed")
    if report.candidate_policy_failures:
        reasons.append("policy.failed")
    if report.candidate_unrelated_quality_ppm + policy.maximum_unrelated_regression_ppm < (
        report.baseline_unrelated_quality_ppm
    ):
        reasons.append("quality.unrelated_regression")
    if report.candidate_p95_latency_microseconds > policy.maximum_p95_latency_microseconds:
        reasons.append("latency.maximum_exceeded")
    if _regressed(
        report.candidate_p95_latency_microseconds,
        report.baseline_p95_latency_microseconds,
        policy.maximum_latency_regression_ppm,
    ):
        reasons.append("latency.regressed")
    for code, candidate, baseline, maximum in (
        ("ram", report.candidate_peak_ram_bytes, report.baseline_peak_ram_bytes,
         policy.maximum_peak_ram_bytes),
        ("vram", report.candidate_peak_vram_bytes, report.baseline_peak_vram_bytes,
         policy.maximum_peak_vram_bytes),
        ("energy", report.candidate_energy_joules, report.baseline_energy_joules,
         policy.maximum_energy_joules),
    ):
        if candidate > maximum:
            reasons.append(f"resource.{code}_maximum_exceeded")
        if _regressed(candidate, baseline, policy.maximum_resource_regression_ppm):
            reasons.append(f"resource.{code}_regressed")
    if report.candidate_adapter_bytes > policy.maximum_adapter_bytes:
        reasons.append("artifact.size_exceeded")
    if report.candidate_cold_start_microseconds > policy.maximum_cold_start_microseconds:
        reasons.append("latency.cold_start_exceeded")
    if policy.require_scheduler_compatibility and not report.scheduler_compatible:
        reasons.append("scheduler.incompatible")
    reasons_tuple = tuple(sorted(set(reasons)))
    public_key = signing_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    values: dict[str, object] = {
        "decision_id": decision_id, "approval_id": approval.approval_id,
        "evaluation_id": report.evaluation_id,
        "report_sha256": report.report_sha256,
        "promotable": not reasons_tuple, "reason_codes": reasons_tuple,
        "decided_at": decided_at, "signer_key_id": signer_key_id,
        "signer_public_key_base64": base64.b64encode(public_key).decode("ascii"),
    }
    values["decision_sha256"] = _digest(_decision_document(values))
    values["signature_base64"] = base64.b64encode(
        signing_key.sign(_decision_signature_payload(values)),
    ).decode("ascii")
    return ExpertComparisonDecision(**values)  # type: ignore[arg-type]


def evaluation_policy_digest(value: FactoryEvaluationPolicy) -> str:
    return _digest({
        name: field for name, field in _fields(value)
        if name not in {"policy_sha256", "contract_version"}
    })


def evaluation_approval_digest(value: FactoryEvaluationApproval) -> str:
    return _digest(_approval_document(dict(_fields(value))))


def held_out_access_digest(value: HeldOutAccessReceipt) -> str:
    return _digest(_access_document(dict(_fields(value))))


def paired_measurement_digest(value: PairedEvaluationMeasurement) -> str:
    return _digest(_measurement_document(dict(_fields(value))))


def evaluation_report_digest(value: ExpertEvaluationReport) -> str:
    return _digest(_report_document(dict(_fields(value))))


def comparison_decision_digest(value: ExpertComparisonDecision) -> str:
    return _digest(_decision_document(dict(_fields(value))))


def _approval_document(values: dict[str, object]) -> dict[str, object]:
    return _without(values, "approval_sha256", "contract_version")


def _access_document(values: dict[str, object]) -> dict[str, object]:
    return _without(values, "receipt_sha256", "contract_version")


def _measurement_document(values: dict[str, object]) -> dict[str, object]:
    return _without(values, "measurement_sha256", "contract_version")


def _report_document(values: dict[str, object]) -> dict[str, object]:
    return _without(values, "report_sha256", "contract_version")


def _decision_document(values: dict[str, object]) -> dict[str, object]:
    return _without(
        values, "decision_sha256", "signature_base64", "contract_version",
    )


def _decision_signature_payload(values: dict[str, object]) -> bytes:
    document = _without(values, "signature_base64", "contract_version")
    return json.dumps(
        _canonical(document), sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _verify_decision_signature(value: ExpertComparisonDecision) -> None:
    try:
        public_key = base64.b64decode(value.signer_public_key_base64, validate=True)
        signature = base64.b64decode(value.signature_base64, validate=True)
        if len(public_key) != 32 or len(signature) != 64:
            raise ValueError("evaluation decision signature has invalid length")
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature,
            _decision_signature_payload(dict(_fields(value))),
        )
    except (InvalidSignature, binascii.Error, TypeError, ValueError) as error:
        raise ValueError("evaluation decision signature is invalid") from error


def _without(values: dict[str, object], *names: str) -> dict[str, object]:
    return {name: _canonical(field) for name, field in values.items() if name not in names}


def _canonical(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _canonical(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    if isinstance(value, tuple):
        return tuple(_canonical(item) for item in value)
    return value


def _fields(value: object) -> tuple[tuple[str, object], ...]:
    return tuple(
        (name, getattr(value, name))
        for name in value.__dataclass_fields__  # type: ignore[attr-defined]
    )


def _wilson_bounds(passes: int, count: int, z_ppm: int) -> tuple[int, int]:
    if count < 1:
        return 0, 0
    z = z_ppm / 1_000_000
    rate = passes / count
    denominator = 1 + z * z / count
    center = (rate + z * z / (2 * count)) / denominator
    margin = z * math.sqrt(
        rate * (1 - rate) / count + z * z / (4 * count * count)
    ) / denominator
    return max(0, round((center - margin) * 1_000_000)), min(
        1_000_000, round((center + margin) * 1_000_000),
    )


def _rate(passes: int, count: int) -> int:
    return 0 if count == 0 else round(passes * 1_000_000 / count)


def _passed_rate(values: tuple[PairedEvaluationMeasurement, ...], candidate: bool) -> int:
    return _rate(sum(
        item.candidate_passed if candidate else item.baseline_passed for item in values
    ), len(values))


def _failures(
    values: tuple[PairedEvaluationMeasurement, ...],
    kind: EvaluationCaseKind, candidate: bool,
) -> int:
    return sum(
        not (item.candidate_passed if candidate else item.baseline_passed)
        for item in values if item.kind is kind
    )


def _percentile(values: tuple[int, ...], percentile: int) -> int:
    ordered = tuple(sorted(values))
    return ordered[max(0, math.ceil(len(ordered) * percentile / 100) - 1)]


def _regressed(candidate: int, baseline: int, allowed_ppm: int) -> bool:
    if baseline == 0:
        return candidate > 0
    return candidate * 1_000_000 > baseline * (1_000_000 + allowed_ppm)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        _canonical(value), sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} is invalid")


def _sha(value: str, name: str) -> None:
    if len(value) != 64 or any(item not in "0123456789abcdef" for item in value):
        raise ValueError(f"{name} must be lowercase SHA-256")


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("evaluation timestamp must be timezone-aware")


def _version(value: str) -> None:
    if value != FACTORY_EVALUATION_VERSION:
        raise ValueError("unsupported factory evaluation contract version")
