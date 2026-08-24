"""Durable lifecycle contract for an owner-approved peer enrollment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.fabric.pairing import DevicePairingApproval

PEER_ENROLLMENT_CONTRACT_VERSION = "fam.fabric.peer-enrollment/v1alpha1"


class PeerEnrollmentState(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class PeerEnrollmentRecord:
    enrollment_id: str
    approval: DevicePairingApproval
    state: PeerEnrollmentState
    revision: int
    enrolled_at: datetime
    revoked_at: datetime | None = None
    reason_codes: tuple[str, ...] = ()
    contract_version: str = PEER_ENROLLMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.enrollment_id.strip() or self.revision < 1:
            raise ValueError("peer enrollment identity or revision is invalid")
        if self.enrolled_at.tzinfo is None or self.enrolled_at.utcoffset() is None:
            raise ValueError("peer enrollment timestamp must be timezone-aware")
        if (self.state is PeerEnrollmentState.REVOKED) != (self.revoked_at is not None):
            raise ValueError("peer enrollment state and revocation disagree")
        if self.revoked_at is not None:
            if self.revoked_at.tzinfo is None or self.revoked_at.utcoffset() is None:
                raise ValueError("peer revocation timestamp must be timezone-aware")
            if self.revoked_at < self.enrolled_at or not self.reason_codes:
                raise ValueError("peer revocation evidence is invalid")
        if any(not reason.strip() or len(reason) > 128 for reason in self.reason_codes):
            raise ValueError("peer enrollment reason code is invalid")
        if self.contract_version != PEER_ENROLLMENT_CONTRACT_VERSION:
            raise ValueError("peer enrollment contract is unsupported")

    @property
    def active(self) -> bool:
        return self.state is PeerEnrollmentState.ACTIVE
