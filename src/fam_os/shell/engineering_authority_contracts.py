"""Typed Shell contracts for owner engineering authority ceremonies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering.break_glass import BreakGlassChallenge, BreakGlassDecision
from fam_os.core.engineering.grants import (
    EngineeringAuthorityGrant,
    EngineeringAuthorizationDecision,
    OwnerGrantApproval,
)


SHELL_ENGINEERING_AUTHORITY_VERSION = "fam.shell.engineering-authority/v1alpha1"


class ShellEngineeringAuthorityOperation(StrEnum):
    ISSUE_CONTEXT = "issue_context"
    ACTIVATE = "activate"
    INSPECT = "inspect"
    AUDIT = "audit"
    REVOKE = "revoke"


@dataclass(frozen=True, slots=True)
class ShellEngineeringContextRequest:
    request_id: str
    authority_session_id: str
    owner_id: str
    purpose: str
    payload_sha256: str
    confirmed: bool
    contract_version: str = SHELL_ENGINEERING_AUTHORITY_VERSION

    def __post_init__(self) -> None:
        for name in ("request_id", "authority_session_id", "owner_id", "purpose"):
            _text(getattr(self, name), name)
        _digest(self.payload_sha256)
        _boolean(self.confirmed, "confirmed")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellEngineeringActivationRequest:
    request_id: str
    authority_session_id: str
    grant: EngineeringAuthorityGrant
    approval: OwnerGrantApproval
    challenge: BreakGlassChallenge | None
    decision: BreakGlassDecision | None
    confirmed: bool
    contract_version: str = SHELL_ENGINEERING_AUTHORITY_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        _text(self.authority_session_id, "authority_session_id")
        if not isinstance(self.grant, EngineeringAuthorityGrant):
            raise ValueError("Shell engineering grant is invalid")
        if not isinstance(self.approval, OwnerGrantApproval):
            raise ValueError("Shell engineering approval is invalid")
        if self.challenge is not None and not isinstance(self.challenge, BreakGlassChallenge):
            raise ValueError("Shell engineering challenge is invalid")
        if self.decision is not None and not isinstance(self.decision, BreakGlassDecision):
            raise ValueError("Shell engineering decision is invalid")
        if (self.challenge is None) != (self.decision is None):
            raise ValueError("Shell engineering break-glass pair is incomplete")
        _boolean(self.confirmed, "confirmed")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellEngineeringGrantQuery:
    request_id: str
    operation: ShellEngineeringAuthorityOperation
    grant_id: str
    contract_version: str = SHELL_ENGINEERING_AUTHORITY_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        _text(self.grant_id, "grant_id")
        if not isinstance(self.operation, ShellEngineeringAuthorityOperation):
            raise ValueError("Shell engineering query operation is invalid")
        if self.operation not in {
            ShellEngineeringAuthorityOperation.INSPECT,
            ShellEngineeringAuthorityOperation.AUDIT,
        }:
            raise ValueError("Shell engineering query operation is invalid")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellEngineeringRevocationRequest:
    request_id: str
    grant_id: str
    owner_id: str
    confirmed: bool
    contract_version: str = SHELL_ENGINEERING_AUTHORITY_VERSION

    def __post_init__(self) -> None:
        for name in ("request_id", "grant_id", "owner_id"):
            _text(getattr(self, name), name)
        _boolean(self.confirmed, "confirmed")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellEngineeringAuthorityResponse:
    request_id: str
    operation: ShellEngineeringAuthorityOperation
    context_id: str | None = None
    expires_at: datetime | None = None
    grant: EngineeringAuthorityGrant | None = None
    reconfirmation_required: bool | None = None
    usable: bool | None = None
    decisions: tuple[EngineeringAuthorizationDecision, ...] = ()
    contract_version: str = SHELL_ENGINEERING_AUTHORITY_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        if not isinstance(self.operation, ShellEngineeringAuthorityOperation):
            raise ValueError("Shell engineering response operation is invalid")
        if self.operation is ShellEngineeringAuthorityOperation.ISSUE_CONTEXT:
            valid = self.context_id is not None and self.expires_at is not None
            valid = valid and self.grant is None and not self.decisions
            valid = valid and self.reconfirmation_required is None and self.usable is None
        elif self.operation is ShellEngineeringAuthorityOperation.AUDIT:
            valid = self.context_id is None and self.expires_at is None
            valid = valid and self.grant is None
            valid = valid and self.reconfirmation_required is None and self.usable is None
        else:
            valid = self.operation in {
                ShellEngineeringAuthorityOperation.ACTIVATE,
                ShellEngineeringAuthorityOperation.INSPECT,
                ShellEngineeringAuthorityOperation.REVOKE,
            }
            valid = valid and self.grant is not None and not self.decisions
            valid = valid and self.context_id is None and self.expires_at is None
            valid = valid and type(self.reconfirmation_required) is bool
            valid = valid and type(self.usable) is bool
        if not valid:
            raise ValueError("Shell engineering authority response shape is invalid")
        if self.expires_at is not None and (
            self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None
        ):
            raise ValueError("Shell engineering context expiry must be timezone-aware")
        _version(self.contract_version)


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Shell engineering {name} must be non-empty text")


def _digest(value: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError("Shell engineering payload digest is invalid")
    int(value, 16)


def _boolean(value: bool, name: str) -> None:
    if type(value) is not bool:
        raise ValueError(f"Shell engineering {name} must be boolean")


def _version(value: str) -> None:
    if value != SHELL_ENGINEERING_AUTHORITY_VERSION:
        raise ValueError("unsupported Shell engineering authority version")
