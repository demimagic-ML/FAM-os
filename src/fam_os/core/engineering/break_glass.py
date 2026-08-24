"""Exact-consequence owner ceremony for exceptional engineering grants."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import hashlib

from fam_os.core.engineering._validation import aware, digest, text, texts, unique_enum
from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.grants import EngineeringGrantScopeKind, VerificationRequirement
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class BreakGlassDisposition(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class BreakGlassChallenge:
    challenge_id: str
    owner_id: str
    grant_id: str
    authorities: tuple[EngineeringAuthority, ...]
    verification: VerificationRequirement
    scope_kind: EngineeringGrantScopeKind
    scope_id: str
    consequences: tuple[str, ...]
    consequences_sha256: str
    issued_at: datetime
    expires_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("challenge_id", "owner_id", "grant_id", "scope_id"):
            text(getattr(self, name), name)
        if not self.authorities:
            raise ValueError("break-glass challenge requires authorities")
        unique_enum(self.authorities, "authorities")
        if not self.consequences:
            raise ValueError("break-glass challenge requires exact consequences")
        texts(self.consequences, "consequences")
        digest(self.consequences_sha256, "consequences_sha256", required=True)
        if self.consequences_sha256 != consequences_digest(self.consequences):
            raise ValueError("break-glass consequences digest does not match")
        aware(self.issued_at, "issued_at")
        aware(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("break-glass challenge expiry must follow issue time")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("break-glass challenge version is unsupported")


@dataclass(frozen=True, slots=True)
class BreakGlassDecision:
    decision_id: str
    challenge_id: str
    owner_id: str
    grant_id: str
    disposition: BreakGlassDisposition
    scope_kind: EngineeringGrantScopeKind
    scope_id: str
    consequences_sha256: str
    decided_at: datetime
    authentication_context_id: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "decision_id", "challenge_id", "owner_id", "grant_id", "scope_id",
            "authentication_context_id",
        ):
            text(getattr(self, name), name)
        digest(self.consequences_sha256, "consequences_sha256", required=True)
        aware(self.decided_at, "decided_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("break-glass decision version is unsupported")


def consequences_digest(consequences: tuple[str, ...]) -> str:
    payload = "\n".join(f"{len(item.encode('utf-8'))}:{item}" for item in consequences)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
