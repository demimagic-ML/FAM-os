"""Ed25519 detached signature verification adapter."""

from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.registry.trust_contracts import SignatureAlgorithm


class Ed25519PackageSignatureVerifier:
    def verify(
        self,
        algorithm: SignatureAlgorithm,
        public_key: bytes,
        message: bytes,
        signature: bytes,
    ) -> bool:
        if algorithm is not SignatureAlgorithm.ED25519:
            return False
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
        except (InvalidSignature, ValueError):
            return False
        return True
