"""Canonical domain-separated bytes covered by package signatures."""

from __future__ import annotations

from fam_os.experts.manifest import ExpertManifest


PACKAGE_SIGNATURE_DOMAIN = b"FAM_OS_EXPERT_PACKAGE_SIGNATURE_V1\x00"
VERIFIER_PACKAGE_SIGNATURE_DOMAIN = b"FAM_OS_VERIFIER_PACKAGE_SIGNATURE_V1\x00"


def expert_package_signing_payload(manifest: ExpertManifest) -> bytes:
    from fam_os.schemas.codec import dumps_document

    return PACKAGE_SIGNATURE_DOMAIN + dumps_document(manifest).encode("utf-8")


def verifier_package_signing_payload(manifest: object) -> bytes:
    """Return domain-separated canonical bytes for a verifier manifest."""
    from fam_os.schemas.codec import dumps_document

    return VERIFIER_PACKAGE_SIGNATURE_DOMAIN + dumps_document(manifest).encode("utf-8")
