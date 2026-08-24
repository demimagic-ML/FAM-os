"""Typed Shell contracts for persistent integration environments."""

from dataclasses import dataclass
from enum import StrEnum

from fam_os.core.engineering import (
    CandidateWorkspace,
    IntegrationEnvironmentPlan,
    IntegrationEnvironmentReceipt,
    IntegrationEnvironmentStartResult,
    IntegrationExecutionPermit,
)


SHELL_INTEGRATION_ENVIRONMENT_VERSION = "fam.shell.integration-environment/v1alpha1"


class ShellIntegrationEnvironmentOperation(StrEnum):
    START = "start"
    LIST = "list"
    INSPECT = "inspect"
    AUDIT = "audit"
    CLEANUP = "cleanup"
    RECONCILE = "reconcile"
    INTENT_LIST = "intent_list"
    INTENT_INSPECT = "intent_inspect"


@dataclass(frozen=True, slots=True)
class ShellIntegrationEnvironmentStartRequest:
    request_id: str
    authority_session_id: str
    owner_id: str
    plan: IntegrationEnvironmentPlan
    candidate: CandidateWorkspace
    grant_id: str
    principal_id: str
    confirmed: bool
    contract_version: str = SHELL_INTEGRATION_ENVIRONMENT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "request_id", "authority_session_id", "owner_id", "grant_id",
            "principal_id",
        ):
            _text(getattr(self, name), name)
        if not isinstance(self.plan, IntegrationEnvironmentPlan):
            raise ValueError("Shell integration plan is invalid")
        if not isinstance(self.candidate, CandidateWorkspace):
            raise ValueError("Shell integration candidate is invalid")
        _confirmed(self.confirmed)
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellIntegrationEnvironmentQuery:
    request_id: str
    operation: ShellIntegrationEnvironmentOperation
    owner_id: str
    environment_id: str | None = None
    contract_version: str = SHELL_INTEGRATION_ENVIRONMENT_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        _text(self.owner_id, "owner_id")
        if self.operation not in {
            ShellIntegrationEnvironmentOperation.LIST,
            ShellIntegrationEnvironmentOperation.INSPECT,
            ShellIntegrationEnvironmentOperation.AUDIT,
            ShellIntegrationEnvironmentOperation.INTENT_LIST,
            ShellIntegrationEnvironmentOperation.INTENT_INSPECT,
        }:
            raise ValueError("Shell integration query operation is invalid")
        requires_identity = self.operation not in {
            ShellIntegrationEnvironmentOperation.LIST,
            ShellIntegrationEnvironmentOperation.INTENT_LIST,
        }
        if requires_identity != (self.environment_id is not None):
            raise ValueError("Shell integration query identity is invalid")
        if self.environment_id is not None:
            _text(self.environment_id, "environment_id")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellIntegrationEnvironmentControlRequest:
    request_id: str
    operation: ShellIntegrationEnvironmentOperation
    owner_id: str
    environment_id: str
    confirmed: bool
    contract_version: str = SHELL_INTEGRATION_ENVIRONMENT_VERSION

    def __post_init__(self) -> None:
        for name in ("request_id", "owner_id", "environment_id"):
            _text(getattr(self, name), name)
        if self.operation not in {
            ShellIntegrationEnvironmentOperation.CLEANUP,
            ShellIntegrationEnvironmentOperation.RECONCILE,
        }:
            raise ValueError("Shell integration control operation is invalid")
        _confirmed(self.confirmed)
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellIntegrationEnvironmentRecord:
    state: str
    plan: IntegrationEnvironmentPlan
    candidate: CandidateWorkspace
    start_result: IntegrationEnvironmentStartResult
    latest_receipt: IntegrationEnvironmentReceipt

    def __post_init__(self) -> None:
        if self.state not in {"active", "failed", "cleaned"}:
            raise ValueError("Shell integration state is invalid")
        identity = self.plan.environment_id
        if (
            self.start_result.environment_id != identity
            or self.latest_receipt.environment_id != identity
            or self.candidate.candidate_id != self.plan.candidate_id
        ):
            raise ValueError("Shell integration record identities do not match")


@dataclass(frozen=True, slots=True)
class ShellIntegrationStartIntentRecord:
    state: str
    plan: IntegrationEnvironmentPlan
    candidate: CandidateWorkspace
    permit: IntegrationExecutionPermit | None = None
    recovery_receipt: IntegrationEnvironmentReceipt | None = None

    def __post_init__(self) -> None:
        if self.state not in {
            "starting", "recovery_required", "prelaunch_failed",
            "recovered", "committed",
        }:
            raise ValueError("Shell integration start-intent state is invalid")
        if (
            self.candidate.candidate_id != self.plan.candidate_id
            or self.candidate.candidate_workspace != self.plan.candidate_root
            or (self.permit is not None and self.permit.environment_id != self.plan.environment_id)
            or (
                self.recovery_receipt is not None
                and self.recovery_receipt.environment_id != self.plan.environment_id
            )
        ):
            raise ValueError("Shell integration start-intent identities do not match")
        if self.state == "prelaunch_failed" and self.permit is not None:
            raise ValueError("prelaunch-failed intent cannot contain a permit")
        if self.state in {"recovery_required", "recovered", "committed"} and self.permit is None:
            raise ValueError("permitted integration intent lacks its permit")
        if (self.state == "recovered") != (self.recovery_receipt is not None):
            raise ValueError("integration recovery receipt and state disagree")


@dataclass(frozen=True, slots=True)
class ShellIntegrationEnvironmentResponse:
    request_id: str
    operation: ShellIntegrationEnvironmentOperation
    record: ShellIntegrationEnvironmentRecord | None = None
    records: tuple[ShellIntegrationEnvironmentRecord, ...] = ()
    start_result: IntegrationEnvironmentStartResult | None = None
    receipt: IntegrationEnvironmentReceipt | None = None
    receipts: tuple[IntegrationEnvironmentReceipt, ...] = ()
    intent_record: ShellIntegrationStartIntentRecord | None = None
    intent_records: tuple[ShellIntegrationStartIntentRecord, ...] = ()
    contract_version: str = SHELL_INTEGRATION_ENVIRONMENT_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        shapes = {
            ShellIntegrationEnvironmentOperation.START: self.start_result is not None,
            ShellIntegrationEnvironmentOperation.LIST: True,
            ShellIntegrationEnvironmentOperation.INSPECT: self.record is not None,
            ShellIntegrationEnvironmentOperation.AUDIT: bool(self.receipts),
            ShellIntegrationEnvironmentOperation.CLEANUP: self.receipt is not None,
            ShellIntegrationEnvironmentOperation.RECONCILE: self.receipt is not None,
            ShellIntegrationEnvironmentOperation.INTENT_LIST: True,
            ShellIntegrationEnvironmentOperation.INTENT_INSPECT: self.intent_record is not None,
        }
        if not isinstance(self.operation, ShellIntegrationEnvironmentOperation):
            raise ValueError("Shell integration response operation is invalid")
        populated = (
            self.record is not None, bool(self.records), self.start_result is not None,
            self.receipt is not None, bool(self.receipts),
            self.intent_record is not None, bool(self.intent_records),
        )
        expected_counts = {
            ShellIntegrationEnvironmentOperation.LIST: int(bool(self.records)),
            ShellIntegrationEnvironmentOperation.INTENT_LIST: int(bool(self.intent_records)),
        }
        expected = expected_counts.get(self.operation, 1)
        if not shapes[self.operation] or sum(populated) != expected:
            raise ValueError("Shell integration response shape is invalid")
        _version(self.contract_version)


def _text(value, name) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Shell integration {name} must be non-empty text")


def _confirmed(value) -> None:
    if value is not True:
        raise ValueError("Shell integration action requires confirmation")


def _version(value) -> None:
    if value != SHELL_INTEGRATION_ENVIRONMENT_VERSION:
        raise ValueError("unsupported Shell integration environment version")
