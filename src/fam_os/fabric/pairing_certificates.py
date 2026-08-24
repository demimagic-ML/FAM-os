"""Certificate validation shared by pairing and mutual-TLS trust."""

from __future__ import annotations

import base64
from datetime import datetime

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.fabric.identity import DeviceIdentity
from fam_os.fabric.certificate_validity import certificate_valid_at


def validate_identity_certificate(
    identity: DeviceIdentity,
    certificate_base64: str,
    *,
    observed_at: datetime,
) -> x509.Certificate:
    certificate = x509.load_der_x509_certificate(
        base64.b64decode(certificate_base64, validate=True),
    )
    public = Ed25519PublicKey.from_public_bytes(
        base64.b64decode(identity.public_key_base64, validate=True),
    )
    if _raw_public(certificate.public_key()) != _raw_public(public):
        raise ValueError("pairing certificate does not match identity")
    public.verify(certificate.signature, certificate.tbs_certificate_bytes)
    if certificate_device(certificate) != identity.device_id:
        raise ValueError("pairing certificate has the wrong device binding")
    if not certificate_valid_at(certificate, observed_at):
        raise ValueError("pairing identity certificate is expired")
    constraints = certificate.extensions.get_extension_for_class(x509.BasicConstraints).value
    if not constraints.ca or constraints.path_length != 0:
        raise ValueError("pairing identity certificate is not a bounded trust anchor")
    return certificate


def certificate_device(certificate: x509.Certificate) -> str:
    values = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    uris = values.get_values_for_type(x509.UniformResourceIdentifier)
    if len(uris) != 1 or not uris[0].startswith("urn:fam-os:device-"):
        raise ValueError("pairing certificate device SAN is invalid")
    return uris[0].removeprefix("urn:fam-os:")


def _raw_public(key) -> bytes:
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("pairing identity must use Ed25519")
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
