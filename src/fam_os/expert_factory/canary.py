"""One-use specialist canary and separately signed activation decision."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


FACTORY_CANARY_VERSION = "fam.factory.canary/v1alpha1"
_DOMAIN = b"FAM_OS_FACTORY_CANARY_ACTIVATION_V1\x00"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


class FactoryCanaryStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class FactoryCanaryApproval:
    approval_id: str
    release_id: str
    package_receipt_sha256: str
    package_id: str
    package_version: str
    expert_id: str
    runtime_model_ref: str
    capability_id: str
    verifier_id: str
    suite_sha256: str
    case_count: int
    maximum_output_tokens: int
    maximum_wall_seconds: int
    maximum_ram_bytes: int
    maximum_vram_bytes: int
    one_use_canary_id: str
    issued_at: datetime
    expires_at: datetime
    revision: int
    active: bool
    approval_sha256: str
    contract_version: str = FACTORY_CANARY_VERSION

    def __post_init__(self) -> None:
        for value in (
            self.approval_id, self.release_id, self.package_id,
            self.package_version, self.expert_id, self.runtime_model_ref,
            self.capability_id, self.verifier_id, self.one_use_canary_id,
        ):
            _identifier(value)
        _sha(self.package_receipt_sha256)
        _sha(self.suite_sha256)
        _sha(self.approval_sha256)
        if not 1 <= self.case_count <= 100:
            raise ValueError("factory canary case count is invalid")
        if not 1 <= self.maximum_output_tokens <= 4096:
            raise ValueError("factory canary output bound is invalid")
        if (
            not 10 <= self.maximum_wall_seconds <= 3600
            or self.maximum_ram_bytes < 256 * 1024**2
            or self.maximum_vram_bytes < 0
            or self.revision < 1
            or not self.active
        ):
            raise ValueError("factory canary resource bound is invalid")
        _aware(self.issued_at)
        _aware(self.expires_at)
        if self.expires_at <= self.issued_at:
            raise ValueError("factory canary expiry is invalid")
        if self.approval_sha256 != canary_approval_digest(self):
            raise ValueError("factory canary approval digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class FactoryCanaryReport:
    report_id: str
    approval_id: str
    canary_id: str
    package_receipt_sha256: str
    suite_sha256: str
    runtime_manifest_sha256: str
    status: FactoryCanaryStatus
    reason_code: str
    case_count: int
    passed_case_count: int
    verifier_failure_count: int
    scheduler_selected_declared_capability: bool
    scheduler_excluded_unrelated_capabilities: bool
    outputs_discarded: bool
    peak_ram_bytes: int
    peak_vram_bytes: int
    started_at: datetime
    finished_at: datetime
    report_sha256: str
    contract_version: str = FACTORY_CANARY_VERSION

    def __post_init__(self) -> None:
        for value in (
            self.report_id, self.approval_id, self.canary_id,
            self.reason_code,
        ):
            _identifier(value)
        for value in (
            self.package_receipt_sha256, self.suite_sha256,
            self.runtime_manifest_sha256, self.report_sha256,
        ):
            _sha(value)
        if (
            self.case_count < 1
            or not 0 <= self.passed_case_count <= self.case_count
            or not 0 <= self.verifier_failure_count <= self.case_count
            or min(self.peak_ram_bytes, self.peak_vram_bytes) < 0
        ):
            raise ValueError("factory canary measurements are invalid")
        _aware(self.started_at)
        _aware(self.finished_at)
        if self.finished_at < self.started_at:
            raise ValueError("factory canary time range is invalid")
        if self.report_sha256 != canary_report_digest(self):
            raise ValueError("factory canary report digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class FactoryActivationDecision:
    decision_id: str
    approval_id: str
    canary_id: str
    report_sha256: str
    package_receipt_sha256: str
    activate: bool
    reason_codes: tuple[str, ...]
    signer_key_id: str
    signer_public_key_base64: str
    signature_base64: str
    decided_at: datetime
    decision_sha256: str
    contract_version: str = FACTORY_CANARY_VERSION

    def __post_init__(self) -> None:
        for value in (
            self.decision_id, self.approval_id, self.canary_id,
            self.signer_key_id,
        ):
            _identifier(value)
        _sha(self.report_sha256)
        _sha(self.package_receipt_sha256)
        _sha(self.decision_sha256)
        if len(set(self.reason_codes)) != len(self.reason_codes) or any(
            _ID.fullmatch(reason) is None for reason in self.reason_codes
        ):
            raise ValueError("factory activation reasons are invalid")
        if self.activate == bool(self.reason_codes):
            raise ValueError("factory activation decision reasons are inconsistent")
        public_key = _decode(self.signer_public_key_base64, 32, "public key")
        signature = _decode(self.signature_base64, 64, "signature")
        _aware(self.decided_at)
        if self.decision_sha256 != activation_decision_digest(self):
            raise ValueError("factory activation decision digest does not match")
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(
                signature, _DOMAIN + bytes.fromhex(self.decision_sha256),
            )
        except InvalidSignature as error:
            raise ValueError("factory activation signature is invalid") from error
        _version(self.contract_version)


def build_canary_approval(**values: object) -> FactoryCanaryApproval:
    document = dict(values)
    document.setdefault("revision", 1)
    document.setdefault("active", True)
    document["approval_sha256"] = _digest(document)
    return FactoryCanaryApproval(**document)  # type: ignore[arg-type]


def build_canary_report(**values: object) -> FactoryCanaryReport:
    document = dict(values)
    document["report_sha256"] = _digest(document)
    return FactoryCanaryReport(**document)  # type: ignore[arg-type]


def decide_canary_activation(
    *, decision_id: str, approval: FactoryCanaryApproval,
    report: FactoryCanaryReport, signer_key_id: str,
    signing_key: Ed25519PrivateKey, decided_at: datetime,
) -> FactoryActivationDecision:
    if (
        report.approval_id != approval.approval_id
        or report.canary_id != approval.one_use_canary_id
        or report.package_receipt_sha256 != approval.package_receipt_sha256
        or report.suite_sha256 != approval.suite_sha256
        or report.case_count != approval.case_count
    ):
        raise ValueError("factory canary report does not match approval")
    reasons = []
    if report.status is not FactoryCanaryStatus.COMPLETED:
        reasons.append("canary.incomplete")
    if report.passed_case_count != report.case_count:
        reasons.append("canary.case_failed")
    if report.verifier_failure_count:
        reasons.append("canary.verifier_failed")
    if not report.scheduler_selected_declared_capability:
        reasons.append("canary.scheduler_selection_failed")
    if not report.scheduler_excluded_unrelated_capabilities:
        reasons.append("canary.scheduler_scope_failed")
    if not report.outputs_discarded:
        reasons.append("canary.output_retained")
    if report.peak_ram_bytes > approval.maximum_ram_bytes:
        reasons.append("canary.ram_exceeded")
    if report.peak_vram_bytes > approval.maximum_vram_bytes:
        reasons.append("canary.vram_exceeded")
    body: dict[str, object] = {
        "decision_id": decision_id, "approval_id": approval.approval_id,
        "canary_id": approval.one_use_canary_id,
        "report_sha256": report.report_sha256,
        "package_receipt_sha256": approval.package_receipt_sha256,
        "activate": not reasons, "reason_codes": tuple(reasons),
        "signer_key_id": signer_key_id,
        "decided_at": decided_at,
    }
    digest = _digest(body)
    public = signing_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    return FactoryActivationDecision(
        **body,  # type: ignore[arg-type]
        signer_public_key_base64=base64.b64encode(public).decode("ascii"),
        signature_base64=base64.b64encode(
            signing_key.sign(_DOMAIN + bytes.fromhex(digest)),
        ).decode("ascii"),
        decision_sha256=digest,
    )


def canary_approval_digest(value: FactoryCanaryApproval) -> str:
    return _digest(_without(_fields(value), "approval_sha256", "contract_version"))


def canary_report_digest(value: FactoryCanaryReport) -> str:
    return _digest(_without(_fields(value), "report_sha256", "contract_version"))


def activation_decision_digest(value: FactoryActivationDecision) -> str:
    return _digest(_without(
        _fields(value), "signer_public_key_base64", "signature_base64",
        "decision_sha256", "contract_version",
    ))


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
    if isinstance(value, StrEnum):
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


def _decode(value: str, length: int, label: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError(f"factory activation {label} is invalid") from error
    if len(decoded) != length:
        raise ValueError(f"factory activation {label} length is invalid")
    return decoded


def _identifier(value: str) -> None:
    if _ID.fullmatch(value) is None:
        raise ValueError("factory canary identifier is invalid")


def _sha(value: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError("factory canary digest must be lowercase SHA-256")


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("factory canary timestamp must be timezone-aware")


def _version(value: str) -> None:
    if value != FACTORY_CANARY_VERSION:
        raise ValueError("unsupported factory canary contract version")
