"""Replaceable package-integrity mechanism ports."""

from __future__ import annotations

from typing import Protocol

from fam_os.registry.trust_contracts import SignatureAlgorithm


class PackageSignatureVerifier(Protocol):
    def verify(
        self,
        algorithm: SignatureAlgorithm,
        public_key: bytes,
        message: bytes,
        signature: bytes,
    ) -> bool: ...
