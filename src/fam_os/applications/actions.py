"""Prepared, confirmed, reversible, and verified application actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from fam_os.applications.failures import ApplicationFailure, ApplicationFailureCategory
from fam_os.applications.identifiers import require_identifier, require_text
from fam_os.applications.payloads import JsonObject, freeze_payload
from fam_os.applications.policy import ConfirmationPolicy, Reversibility
from fam_os.applications.timestamps import require_aware_datetime


@dataclass(frozen=True, slots=True)
class ConditionRequirement:
    condition_id: str
    verifier_id: str
    description: str

    def __post_init__(self) -> None:
        for field_name in ("condition_id", "verifier_id"):
            object.__setattr__(
                self, field_name, require_identifier(getattr(self, field_name), field_name)
            )
        object.__setattr__(self, "description", require_text(self.description, "description"))


@dataclass(frozen=True, slots=True)
class ConditionEvidence:
    condition_id: str
    verifier_id: str
    passed: bool
    details: str

    def __post_init__(self) -> None:
        for field_name in ("condition_id", "verifier_id"):
            object.__setattr__(
                self, field_name, require_identifier(getattr(self, field_name), field_name)
            )
        object.__setattr__(self, "details", require_text(self.details, "details"))


@dataclass(frozen=True, slots=True)
class ActionPreparationRequest:
    request_id: str
    instance_id: str
    capability_id: str
    permission_grant_id: str
    summary: str
    parameters: JsonObject = field(default_factory=dict)
    resource_uri: str | None = None
    expected_revision: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("request_id", "instance_id", "capability_id", "permission_grant_id"):
            object.__setattr__(
                self, field_name, require_identifier(getattr(self, field_name), field_name)
            )
        object.__setattr__(self, "summary", require_text(self.summary, "summary"))
        object.__setattr__(self, "parameters", freeze_payload(self.parameters))
        for field_name in ("resource_uri", "expected_revision"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, require_text(value, field_name))


@dataclass(frozen=True, slots=True)
class ActionProposal:
    proposal_id: str
    request: ActionPreparationRequest
    preview: JsonObject
    reversibility: Reversibility
    confirmation: ConfirmationPolicy
    postconditions: tuple[ConditionRequirement, ...]
    preconditions: tuple[ConditionRequirement, ...] = ()
    reversal_capability_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "proposal_id", require_identifier(self.proposal_id, "proposal_id"))
        object.__setattr__(self, "preview", freeze_payload(self.preview))
        if self.reversibility is Reversibility.NOT_APPLICABLE:
            raise ValueError("action proposals must declare reversibility")
        if not self.postconditions:
            raise ValueError("action proposals require postconditions")
        _require_unique_conditions(self.preconditions, "preconditions")
        _require_unique_conditions(self.postconditions, "postconditions")
        if self.reversibility in (Reversibility.REVERSIBLE, Reversibility.COMPENSATABLE):
            if self.reversal_capability_id is None:
                raise ValueError("recoverable proposals require a reversal capability")
        if self.reversal_capability_id is not None:
            object.__setattr__(
                self,
                "reversal_capability_id",
                require_identifier(self.reversal_capability_id, "reversal_capability_id"),
            )
        if (
            self.reversibility is Reversibility.IRREVERSIBLE
            and self.confirmation is not ConfirmationPolicy.ALWAYS
        ):
            raise ValueError("irreversible proposals always require confirmation")


class ConfirmationDecision(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class ActionConfirmation:
    confirmation_id: str
    proposal_id: str
    permission_grant_id: str
    decision: ConfirmationDecision
    decided_by: str
    decided_at: datetime
    reason: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "confirmation_id",
            "proposal_id",
            "permission_grant_id",
            "decided_by",
        ):
            object.__setattr__(
                self, field_name, require_identifier(getattr(self, field_name), field_name)
            )
        require_aware_datetime(self.decided_at, "decided_at")
        if self.reason is not None:
            object.__setattr__(self, "reason", require_text(self.reason, "reason"))
        if self.decision is ConfirmationDecision.DENIED and self.reason is None:
            raise ValueError("denied confirmations require a reason")


class ActionStatus(StrEnum):
    VERIFIED = "verified"
    DENIED = "denied"
    PRECONDITION_FAILED = "precondition_failed"
    EXECUTION_FAILED = "execution_failed"
    POSTCONDITION_FAILED = "postcondition_failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ActionResult:
    proposal_id: str
    status: ActionStatus
    completed_at: datetime
    postcondition_evidence: tuple[ConditionEvidence, ...] = ()
    output: JsonObject = field(default_factory=dict)
    before_revision: str | None = None
    after_revision: str | None = None
    reversal_token: str | None = None
    error: ApplicationFailure | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "proposal_id", require_identifier(self.proposal_id, "proposal_id"))
        require_aware_datetime(self.completed_at, "completed_at")
        object.__setattr__(self, "output", freeze_payload(self.output))
        _require_unique_evidence(self.postcondition_evidence)
        for field_name in ("before_revision", "after_revision", "reversal_token"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, require_text(value, field_name))
        self._validate_status()

    @property
    def verified(self) -> bool:
        return self.status is ActionStatus.VERIFIED

    def _validate_status(self) -> None:
        if self.verified:
            if not self.postcondition_evidence:
                raise ValueError("verified actions require postcondition evidence")
            if not all(item.passed for item in self.postcondition_evidence):
                raise ValueError("verified actions require passing postconditions")
            if self.error is not None:
                raise ValueError("verified actions cannot carry an error")
            return
        if self.status is ActionStatus.POSTCONDITION_FAILED:
            if not any(not item.passed for item in self.postcondition_evidence):
                raise ValueError("postcondition failure requires failed evidence")
        if self.error is None:
            raise ValueError("non-verified actions require an error")
        expected = {
            ActionStatus.DENIED: ApplicationFailureCategory.PERMISSION_DENIED,
            ActionStatus.PRECONDITION_FAILED: ApplicationFailureCategory.PRECONDITION_FAILED,
            ActionStatus.EXECUTION_FAILED: ApplicationFailureCategory.EXECUTION_FAILED,
            ActionStatus.POSTCONDITION_FAILED: ApplicationFailureCategory.POSTCONDITION_FAILED,
            ActionStatus.CANCELLED: ApplicationFailureCategory.CANCELLED,
        }[self.status]
        if self.error.category is not expected:
            raise ValueError("action status must match structured failure category")


def _require_unique_conditions(
    conditions: tuple[ConditionRequirement, ...], field_name: str
) -> None:
    identifiers = tuple(condition.condition_id for condition in conditions)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"{field_name} condition IDs must be unique")


def _require_unique_evidence(evidence: tuple[ConditionEvidence, ...]) -> None:
    identifiers = tuple(item.condition_id for item in evidence)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("postcondition evidence IDs must be unique")
