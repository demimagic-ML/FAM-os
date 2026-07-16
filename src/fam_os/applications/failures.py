"""Structured Application Fabric failure evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from re import fullmatch


APPLICATION_FAILURE_CONTRACT_VERSION = "fam.application.failure/v1alpha1"


class ApplicationFailureCategory(StrEnum):
    PERMISSION_DENIED = "permission_denied"
    UNAVAILABLE = "unavailable"
    PRECONDITION_FAILED = "precondition_failed"
    EXECUTION_FAILED = "execution_failed"
    POSTCONDITION_FAILED = "postcondition_failed"
    CANCELLED = "cancelled"


class ApplicationRetryDisposition(StrEnum):
    NEVER = "never"
    IMMEDIATE = "immediate"
    WITH_BACKOFF = "with_backoff"
    AFTER_USER_ACTION = "after_user_action"
    AFTER_STATE_CHANGE = "after_state_change"


@dataclass(frozen=True, slots=True)
class ApplicationFailure:
    category: ApplicationFailureCategory
    code: str
    safe_message: str
    retry: ApplicationRetryDisposition
    evidence_ids: tuple[str, ...] = ()
    contract_version: str = APPLICATION_FAILURE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        code = self.code.strip().lower()
        message = self.safe_message.strip()
        if fullmatch(r"[a-z][a-z0-9_.-]*", code) is None or "." not in code:
            raise ValueError("application failure code must be a namespaced identifier")
        if not message or len(message) > 500 or any(item in message for item in "\r\n\t"):
            raise ValueError("application failure safe_message must be one bounded line")
        evidence_ids = tuple(item.strip() for item in self.evidence_ids)
        if any(not item for item in evidence_ids) or len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("application failure evidence IDs must be non-empty and unique")
        if self.contract_version != APPLICATION_FAILURE_CONTRACT_VERSION:
            raise ValueError("unsupported application failure contract_version")
        if self.category is ApplicationFailureCategory.PERMISSION_DENIED:
            allowed = {
                ApplicationRetryDisposition.NEVER,
                ApplicationRetryDisposition.AFTER_USER_ACTION,
            }
            if self.retry not in allowed:
                raise ValueError("permission denial retry requires user action or never")
        if self.category is ApplicationFailureCategory.CANCELLED:
            if self.retry is not ApplicationRetryDisposition.NEVER:
                raise ValueError("cancelled application failures cannot retry automatically")
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "safe_message", message)
        object.__setattr__(self, "evidence_ids", evidence_ids)
