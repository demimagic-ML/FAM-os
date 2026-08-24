"""Typed Shell contracts for the persistent master engineering lifecycle."""

from dataclasses import dataclass
from enum import StrEnum

from fam_os.core.engineering import (
    CandidateEditRecord, CandidateVerificationRecord, CandidateChangesetRecord,
    EngineeringIncidentEvidenceReceipt, EngineeringIncidentState,
    EngineeringLoopBudget, EngineeringReviewCheckpoint,
    EngineeringReviewResolutionReceipt, EngineeringReviewSelection,
    EngineeringReviewWaiverDecision,
    EngineeringTaskDefinition, GitPublicationReceipt,
    DocumentationGenerationRequest, DocumentationGovernanceBinding,
    DocumentationRequirementSelection, DocumentationStalenessReport,
    GeneratedDocumentationReceipt, RequirementTraceabilityRecord,
    RuntimeDiagnosticRequest, RuntimeDiagnosticReceipt,
    DatabaseBackupReceipt, DatabaseChangePlan, DatabasePostapplyReceipt,
    DatabaseVerificationReceipt,
)


SHELL_ENGINEERING_LOOP_VERSION = "fam.shell.engineering-loop/v1alpha1"


class ShellEngineeringLoopOperation(StrEnum):
    START = "start"
    LIST = "list"
    INSPECT = "inspect"
    RESUME = "resume"
    PREPARE = "prepare"
    EDIT = "edit"
    EDITS = "edits"
    VERIFY = "verify"
    REVERIFY = "reverify"
    VERIFICATIONS = "verifications"
    PREVIEW = "preview"
    APPLY = "apply"
    CHANGESETS = "changesets"
    PUBLISH = "publish"
    INCIDENTS = "incidents"
    INCIDENT_ADVANCE = "incident_advance"
    REVIEWS = "reviews"
    DOCUMENTATION = "documentation"
    RUNTIME_DIAGNOSTICS = "runtime_diagnostics"
    DATABASE = "database"


@dataclass(frozen=True, slots=True)
class ShellEngineeringLoopStartRequest:
    request_id: str
    owner_id: str
    definition: EngineeringTaskDefinition
    budget: EngineeringLoopBudget
    confirmed: bool
    contract_version: str = SHELL_ENGINEERING_LOOP_VERSION

    def __post_init__(self) -> None:
        for name in ("request_id", "owner_id"):
            _text(getattr(self, name), name)
        if not isinstance(self.definition, EngineeringTaskDefinition):
            raise ValueError("Shell engineering task definition is invalid")
        if self.definition.task.owner_id != self.owner_id:
            raise ValueError("Shell engineering task owner is invalid")
        if not isinstance(self.budget, EngineeringLoopBudget):
            raise ValueError("Shell engineering loop budget is invalid")
        _confirmed(self.confirmed)
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellEngineeringLoopQuery:
    request_id: str
    operation: ShellEngineeringLoopOperation
    owner_id: str
    task_id: str | None = None
    contract_version: str = SHELL_ENGINEERING_LOOP_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        _text(self.owner_id, "owner_id")
        if self.operation not in {
            ShellEngineeringLoopOperation.LIST,
            ShellEngineeringLoopOperation.INSPECT,
            ShellEngineeringLoopOperation.EDITS,
            ShellEngineeringLoopOperation.VERIFICATIONS,
            ShellEngineeringLoopOperation.CHANGESETS,
            ShellEngineeringLoopOperation.INCIDENTS,
            ShellEngineeringLoopOperation.REVIEWS,
            ShellEngineeringLoopOperation.DOCUMENTATION,
            ShellEngineeringLoopOperation.RUNTIME_DIAGNOSTICS,
            ShellEngineeringLoopOperation.DATABASE,
        }:
            raise ValueError("Shell engineering loop query operation is invalid")
        if (self.operation is not ShellEngineeringLoopOperation.LIST) != (self.task_id is not None):
            raise ValueError("Shell engineering loop query identity is invalid")
        if self.task_id is not None:
            _text(self.task_id, "task_id")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellEngineeringLoopMutation:
    request_id: str
    operation: ShellEngineeringLoopOperation
    owner_id: str
    task_id: str
    confirmed: bool = True
    contract_version: str = SHELL_ENGINEERING_LOOP_VERSION

    def __post_init__(self) -> None:
        for name in ("request_id", "owner_id", "task_id"):
            _text(getattr(self, name), name)
        if self.operation not in {
            ShellEngineeringLoopOperation.RESUME,
            ShellEngineeringLoopOperation.PREPARE,
        }:
            raise ValueError("Shell engineering loop mutation operation is invalid")
        _confirmed(self.confirmed)
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellEngineeringLoopView:
    task_id: str
    intent: str
    workspace_roots: tuple[str, ...]
    acceptance_policy_id: str
    stage: str
    revision: int
    task_graph_evidence_id: str | None
    candidate_id: str | None
    diff_checkpoint_id: str | None
    test_receipt_ids: tuple[str, ...]
    runtime_diagnostic_receipt_ids: tuple[str, ...]
    database_receipt_ids: tuple[str, ...]
    database_postapply_receipt_ids: tuple[str, ...]
    integration_environment_receipt_ids: tuple[str, ...]
    integration_environment_postapply_receipt_ids: tuple[str, ...]
    dependency_receipt_ids: tuple[str, ...]
    design_preview_receipt_ids: tuple[str, ...]
    rollback_receipt_ids: tuple[str, ...]
    git_receipt_ids: tuple[str, ...]
    publication_approval_id: str | None
    budget: dict[str, int]

    def __post_init__(self) -> None:
        _text(self.task_id, "task_id")
        _text(self.intent, "intent")
        _text(self.acceptance_policy_id, "acceptance_policy_id")
        if not self.workspace_roots or any(not item.strip() for item in self.workspace_roots):
            raise ValueError("Shell engineering loop workspace roots are invalid")
        _text(self.stage, "stage")
        if self.revision < 0 or any(not isinstance(value, int) for value in self.budget.values()):
            raise ValueError("Shell engineering loop view is invalid")


@dataclass(frozen=True, slots=True)
class ShellEngineeringLoopResponse:
    request_id: str
    operation: ShellEngineeringLoopOperation
    view: ShellEngineeringLoopView | None = None
    views: tuple[ShellEngineeringLoopView, ...] = ()
    edit: CandidateEditRecord | None = None
    edits: tuple[CandidateEditRecord, ...] = ()
    verification: CandidateVerificationRecord | None = None
    verifications: tuple[CandidateVerificationRecord, ...] = ()
    changeset: CandidateChangesetRecord | None = None
    changesets: tuple[CandidateChangesetRecord, ...] = ()
    publication: GitPublicationReceipt | None = None
    incident: EngineeringIncidentState | None = None
    incidents: tuple[EngineeringIncidentState, ...] = ()
    incident_evidence: tuple[EngineeringIncidentEvidenceReceipt, ...] = ()
    reviews: tuple[EngineeringReviewCheckpoint, ...] = ()
    review_evidence: tuple[
        EngineeringReviewSelection | EngineeringReviewResolutionReceipt
        | EngineeringReviewWaiverDecision, ...
    ] = ()
    documentation: tuple[
        DocumentationGenerationRequest | GeneratedDocumentationReceipt
        | DocumentationGovernanceBinding | DocumentationStalenessReport
        | DocumentationRequirementSelection | RequirementTraceabilityRecord, ...
    ] = ()
    runtime_diagnostic_requests: tuple[RuntimeDiagnosticRequest, ...] = ()
    runtime_diagnostics: tuple[RuntimeDiagnosticReceipt, ...] = ()
    database_plans: tuple[DatabaseChangePlan, ...] = ()
    database_backups: tuple[DatabaseBackupReceipt, ...] = ()
    database_verifications: tuple[DatabaseVerificationReceipt, ...] = ()
    database_postapply: tuple[DatabasePostapplyReceipt, ...] = ()
    contract_version: str = SHELL_ENGINEERING_LOOP_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        database_payload = bool(
            self.database_plans or self.database_backups
            or self.database_verifications or self.database_postapply
        )
        if self.operation is ShellEngineeringLoopOperation.DATABASE:
            if (
                self._has_standard_payload() or self.incident is not None
                or self.incidents or self.incident_evidence or self.reviews
                or self.review_evidence or self.documentation
                or self.runtime_diagnostic_requests or self.runtime_diagnostics
            ):
                raise ValueError("Shell database engineering response is invalid")
            _version(self.contract_version)
            return
        if database_payload:
            raise ValueError(
                "Shell database evidence requires its read-only operation"
            )
        if self.operation is ShellEngineeringLoopOperation.RUNTIME_DIAGNOSTICS:
            if (
                self._has_standard_payload() or self.incident is not None
                or self.incidents or self.incident_evidence or self.reviews
                or self.review_evidence or self.documentation
            ):
                raise ValueError("Shell runtime diagnostic response is invalid")
            _version(self.contract_version)
            return
        if self.runtime_diagnostic_requests or self.runtime_diagnostics:
            raise ValueError(
                "Shell runtime diagnostics require their read-only operation"
            )
        if self.operation is ShellEngineeringLoopOperation.DOCUMENTATION:
            if (
                self._has_standard_payload() or self.incident is not None
                or self.incidents or self.incident_evidence or self.reviews
                or self.review_evidence
            ):
                raise ValueError("Shell engineering documentation response is invalid")
            _version(self.contract_version)
            return
        if self.documentation:
            raise ValueError(
                "Shell documentation state requires a documentation operation"
            )
        if self.operation is ShellEngineeringLoopOperation.REVIEWS:
            if (
                self._has_standard_payload() or self.incident is not None
                or self.incidents or self.incident_evidence or self.documentation
            ):
                raise ValueError("Shell engineering review list response is invalid")
            _version(self.contract_version)
            return
        if self.reviews or self.review_evidence:
            raise ValueError("Shell review state requires a review operation")
        if self.operation is ShellEngineeringLoopOperation.INCIDENT_ADVANCE:
            if (
                self.incident is None or self.incidents or self.incident_evidence
                or self._has_standard_payload()
            ):
                raise ValueError("Shell engineering incident response is invalid")
            _version(self.contract_version)
            return
        if self.operation is ShellEngineeringLoopOperation.INCIDENTS:
            if self.incident is not None or self._has_standard_payload():
                raise ValueError("Shell engineering incident list response is invalid")
            _version(self.contract_version)
            return
        if self.incident is not None or self.incidents or self.incident_evidence:
            raise ValueError("Shell incident state requires an incident operation")
        if self.operation is ShellEngineeringLoopOperation.PUBLISH:
            if (
                self.publication is None or self.view is not None or self.views
                or self.edit is not None or self.edits
                or self.verification is not None or self.verifications
                or self.changeset is not None or self.changesets
            ):
                raise ValueError("Shell Git publication response is invalid")
            _version(self.contract_version)
            return
        if self.publication is not None:
            raise ValueError("Shell publication receipt requires publish operation")
        if self.operation is ShellEngineeringLoopOperation.LIST:
            if (
                self.view is not None or self.edit is not None or self.edits
                or self.verification is not None or self.verifications
                or self.changeset is not None or self.changesets
            ):
                raise ValueError("Shell engineering loop list response is invalid")
        elif self.operation is ShellEngineeringLoopOperation.EDIT:
            if (
                self.edit is None or self.view is not None or self.views or self.edits
                or self.verification is not None or self.verifications
                or self.changeset is not None or self.changesets
            ):
                raise ValueError("Shell candidate edit response is invalid")
        elif self.operation is ShellEngineeringLoopOperation.EDITS:
            if (
                self.view is not None or self.views or self.edit is not None
                or self.verification is not None or self.verifications
                or self.changeset is not None or self.changesets
            ):
                raise ValueError("Shell candidate edit list response is invalid")
        elif self.operation in {
            ShellEngineeringLoopOperation.VERIFY,
            ShellEngineeringLoopOperation.REVERIFY,
        }:
            if (
                self.verification is None or self.view is not None or self.views
                or self.edit is not None or self.edits or self.verifications
                or self.changeset is not None or self.changesets
            ):
                raise ValueError("Shell candidate verification response is invalid")
        elif self.operation is ShellEngineeringLoopOperation.VERIFICATIONS:
            if (
                self.verification is not None or self.view is not None or self.views
                or self.edit is not None or self.edits
                or self.changeset is not None or self.changesets
            ):
                raise ValueError("Shell candidate verification list response is invalid")
        elif self.operation in {
            ShellEngineeringLoopOperation.PREVIEW,
            ShellEngineeringLoopOperation.APPLY,
        }:
            if (
                self.changeset is None or self.view is not None or self.views
                or self.edit is not None or self.edits
                or self.verification is not None or self.verifications
                or self.changesets
            ):
                raise ValueError("Shell candidate changeset response is invalid")
        elif self.operation is ShellEngineeringLoopOperation.CHANGESETS:
            if (
                self.changeset is not None or self.view is not None or self.views
                or self.edit is not None or self.edits
                or self.verification is not None or self.verifications
            ):
                raise ValueError("Shell candidate changeset list response is invalid")
        elif (
            self.view is None or self.views or self.edit is not None or self.edits
            or self.verification is not None or self.verifications
            or self.changeset is not None or self.changesets
        ):
            raise ValueError("Shell engineering loop response is invalid")
        _version(self.contract_version)

    def _has_standard_payload(self) -> bool:
        return bool(
            self.view is not None or self.views
            or self.edit is not None or self.edits
            or self.verification is not None or self.verifications
            or self.changeset is not None or self.changesets
            or self.publication is not None
        )


def _text(value, name) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Shell engineering loop {name} must be non-empty text")


def _confirmed(value) -> None:
    if value is not True:
        raise ValueError("Shell engineering loop mutation requires confirmation")


def _version(value) -> None:
    if value != SHELL_ENGINEERING_LOOP_VERSION:
        raise ValueError("unsupported Shell engineering loop version")
