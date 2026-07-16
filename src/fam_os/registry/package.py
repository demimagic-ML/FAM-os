"""Provider-neutral package identity and trust metadata."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PackageTrustLevel(StrEnum):
    BUILT_IN = "built_in"
    SIGNED = "signed"
    LOCAL_UNVERIFIED = "local_unverified"


@dataclass(frozen=True, slots=True)
class ArtifactDigest:
    algorithm: str
    value: str

    def __post_init__(self) -> None:
        algorithm = self.algorithm.strip().lower()
        value = self.value.strip().lower()
        if not algorithm or not value:
            raise ValueError("artifact digest algorithm and value must not be empty")
        if len(value) < 32 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("artifact digest value must be at least 32 hexadecimal characters")
        object.__setattr__(self, "algorithm", algorithm)
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class PackageMetadata:
    package_id: str
    package_version: str
    publisher_id: str
    license_id: str
    trust_level: PackageTrustLevel
    artifact_digest: ArtifactDigest
    signature_key_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("package_id", "package_version", "publisher_id", "license_id"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")
        if self.signature_key_id is not None and not self.signature_key_id.strip():
            raise ValueError("signature_key_id must not be empty when provided")
        if self.trust_level is PackageTrustLevel.SIGNED and self.signature_key_id is None:
            raise ValueError("signed packages require signature_key_id")
        if self.trust_level is PackageTrustLevel.LOCAL_UNVERIFIED and self.signature_key_id:
            raise ValueError("local unverified packages cannot claim a signature key")
