"""Versioned package signature, trust-policy, and validation evidence contracts."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from enum import StrEnum

from fam_os.registry.license_policy import validate_spdx_expression
from fam_os.registry.package import ArtifactDigest, PackageTrustLevel


REGISTRY_TRUST_CONTRACT_VERSION = "fam.registry.trust/v1alpha1"


class SignatureAlgorithm(StrEnum):
    ED25519 = "ed25519"


class PublisherKeyStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class PackageSignature:
    key_id: str
    algorithm: SignatureAlgorithm
    signature_base64: str
    contract_version: str = REGISTRY_TRUST_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_contract(self.contract_version)
        _require_text(self.key_id, "signature key_id")
        if len(_decode_base64(self.signature_base64, "signature")) != 64:
            raise ValueError("Ed25519 signature must be 64 bytes")

    def signature_bytes(self) -> bytes:
        return _decode_base64(self.signature_base64, "signature")


@dataclass(frozen=True, slots=True)
class TrustedPublisherKey:
    key_id: str
    publisher_id: str
    algorithm: SignatureAlgorithm
    public_key_base64: str
    status: PublisherKeyStatus = PublisherKeyStatus.ACTIVE

    def __post_init__(self) -> None:
        _require_text(self.key_id, "publisher key_id")
        _require_text(self.publisher_id, "publisher_id")
        if len(_decode_base64(self.public_key_base64, "public key")) != 32:
            raise ValueError("Ed25519 public key must be 32 bytes")

    def public_key_bytes(self) -> bytes:
        return _decode_base64(self.public_key_base64, "public key")


@dataclass(frozen=True, slots=True)
class BuiltInPackageAnchor:
    package_id: str
    package_version: str
    publisher_id: str
    artifact_digest: ArtifactDigest

    def __post_init__(self) -> None:
        for name in ("package_id", "package_version", "publisher_id"):
            _require_text(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class PackageTrustPolicy:
    policy_id: str
    allowed_license_expressions: tuple[str, ...]
    publisher_keys: tuple[TrustedPublisherKey, ...] = ()
    built_in_anchors: tuple[BuiltInPackageAnchor, ...] = ()
    allow_license_references: bool = False
    allow_local_unverified: bool = False
    contract_version: str = REGISTRY_TRUST_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_contract(self.contract_version)
        _require_text(self.policy_id, "policy_id")
        _require_unique("allowed licenses", self.allowed_license_expressions)
        for expression in self.allowed_license_expressions:
            validate_spdx_expression(
                expression,
                allow_references=self.allow_license_references,
            )
        _require_unique(
            "publisher keys",
            tuple(item.key_id for item in self.publisher_keys),
            allow_empty=True,
        )
        coordinates = tuple(
            (item.package_id, item.package_version) for item in self.built_in_anchors
        )
        if len(set(coordinates)) != len(coordinates):
            raise ValueError("built-in package coordinates must be unique")


@dataclass(frozen=True, slots=True)
class PackageValidationReport:
    package_id: str
    package_version: str
    accepted: bool
    reason_code: str
    effective_trust: PackageTrustLevel | None
    observed_artifact_digest: ArtifactDigest
    policy_id: str
    verified_key_id: str | None = None
    contract_version: str = REGISTRY_TRUST_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_contract(self.contract_version)
        for name in ("package_id", "package_version", "reason_code", "policy_id"):
            _require_text(getattr(self, name), name)
        if self.accepted != (self.effective_trust is not None):
            raise ValueError("accepted validation requires an effective trust level")
        if self.accepted != (self.reason_code == "accepted"):
            raise ValueError("accepted validation reason must be exact")
        if self.verified_key_id is not None:
            _require_text(self.verified_key_id, "verified_key_id")
        signed = self.effective_trust is PackageTrustLevel.SIGNED
        if signed != (self.verified_key_id is not None):
            raise ValueError("signed effective trust requires a verified key ID")


def _decode_base64(value: str, name: str) -> bytes:
    if len(value) > 256:
        raise ValueError(f"{name} exceeds encoded size limit")
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError(f"{name} must be strict base64") from error


def _require_contract(value: str) -> None:
    if value != REGISTRY_TRUST_CONTRACT_VERSION:
        raise ValueError("unsupported registry trust contract_version")


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _require_unique(name: str, values: tuple[str, ...], *, allow_empty: bool = False) -> None:
    if (not allow_empty and not values) or any(not value.strip() for value in values):
        raise ValueError(f"{name} must contain non-empty values")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")
