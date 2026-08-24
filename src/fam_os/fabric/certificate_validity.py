"""Version-compatible UTC certificate validity checks."""

from datetime import UTC, datetime

from cryptography import x509


def certificate_valid_at(
    certificate: x509.Certificate, observed_at: datetime,
) -> bool:
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("certificate observation time must be timezone-aware")
    before = _utc_boundary(certificate, "not_valid_before")
    after = _utc_boundary(certificate, "not_valid_after")
    return before <= observed_at.astimezone(UTC) < after


def _utc_boundary(certificate: x509.Certificate, name: str) -> datetime:
    value = getattr(certificate, name + "_utc", None)
    if value is None:
        value = getattr(certificate, name)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
