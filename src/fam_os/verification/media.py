"""Deterministic verification for media-bound exact text observations."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass

from fam_os.verification.declarations import MediaArtifactTextVerification


MEDIA_VERIFICATION_VERSION = "fam.verifier.media/v1alpha1"


@dataclass(frozen=True, slots=True)
class MediaArtifactTextReport:
    verification_id: str
    artifact_sha256: str
    artifact_bytes: int
    artifact_matched: bool
    candidate_binding_matched: bool
    text_matched: bool
    passed: bool
    reason_code: str
    contract_version: str = MEDIA_VERIFICATION_VERSION

    def __post_init__(self) -> None:
        expected = (
            self.artifact_matched
            and self.candidate_binding_matched
            and self.text_matched
        )
        if self.passed != expected:
            raise ValueError("media verification pass must match every check")
        if self.artifact_bytes < 0 or len(self.artifact_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.artifact_sha256
        ):
            raise ValueError("media verification artifact evidence is invalid")
        if not self.verification_id.strip() or not self.reason_code.strip():
            raise ValueError("media verification identity is required")
        if self.contract_version != MEDIA_VERIFICATION_VERSION:
            raise ValueError("unsupported media verification version")


@dataclass(frozen=True, slots=True)
class MediaArtifactTextVerifier:
    def verify(
        self,
        verification_id: str,
        specification: MediaArtifactTextVerification,
        candidate_artifact_sha256: str,
        observed_text: str,
    ) -> MediaArtifactTextReport:
        digest, size = _artifact_digest(specification)
        artifact_matched = digest == specification.artifact_sha256
        candidate_binding = candidate_artifact_sha256 == specification.artifact_sha256
        text_matched = observed_text == specification.expected_text
        passed = artifact_matched and candidate_binding and text_matched
        if not artifact_matched:
            reason = "media.artifact_digest_mismatch"
        elif not candidate_binding:
            reason = "media.candidate_binding_mismatch"
        elif not text_matched:
            reason = "media.observed_text_mismatch"
        else:
            reason = "accepted"
        return MediaArtifactTextReport(
            verification_id, digest, size, artifact_matched,
            candidate_binding, text_matched, passed, reason,
        )


def read_verified_media(specification: MediaArtifactTextVerification) -> bytes:
    """Read exact declared bytes for multimodal inference after digest validation."""
    descriptor = os.open(specification.artifact_path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise ValueError("media artifact must be a regular file")
        if details.st_size < 1 or details.st_size > specification.maximum_artifact_bytes:
            raise ValueError("media artifact size is outside the declared bound")
        chunks = []
        remaining = details.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                raise ValueError("media artifact changed during read")
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
    finally:
        os.close(descriptor)
    if hashlib.sha256(content).hexdigest() != specification.artifact_sha256:
        raise ValueError("media artifact digest does not match declaration")
    return content


def _artifact_digest(specification: MediaArtifactTextVerification) -> tuple[str, int]:
    content = read_verified_media(specification)
    return hashlib.sha256(content).hexdigest(), len(content)
