"""Strict proposal, receipt, and unavailable engineering outcomes."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, digest, text, texts, unique_enum
from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class EngineeringResultKind(StrEnum):
    CHANGESET_PROPOSAL = "changeset_proposal"
    VERIFIED_CHANGESET_RECEIPT = "verified_changeset_receipt"
    PUBLICATION_PROPOSAL = "publication_proposal"
    PUBLICATION_RECEIPT = "publication_receipt"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    EXECUTION_RECORD = "engineering_execution"


@dataclass(frozen=True, slots=True)
class EngineeringProposalResult:
    result_id: str
    task_id: str
    change_set_proposal_id: str
    created_at: datetime
    summary: str
    checkpoint_ids: tuple[str, ...]
    result_kind: EngineeringResultKind = EngineeringResultKind.CHANGESET_PROPOSAL
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("result_id", "task_id", "change_set_proposal_id", "summary"):
            text(getattr(self, name), name)
        aware(self.created_at, "created_at")
        texts(self.checkpoint_ids, "checkpoint_ids")
        _identity(self.result_kind, EngineeringResultKind.CHANGESET_PROPOSAL)
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class VerifiedChangeSetReceipt:
    receipt_id: str
    task_id: str
    proposal_id: str
    before_snapshot_id: str
    after_snapshot_id: str
    completed_at: datetime
    operation_ids: tuple[str, ...]
    tool_run_ids: tuple[str, ...]
    verifier_run_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    changed_paths: tuple[str, ...]
    before_tree_sha256: str
    after_tree_sha256: str
    result_kind: EngineeringResultKind = EngineeringResultKind.VERIFIED_CHANGESET_RECEIPT
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "receipt_id", "task_id", "proposal_id", "before_snapshot_id",
            "after_snapshot_id",
        ):
            text(getattr(self, name), name)
        if self.before_snapshot_id == self.after_snapshot_id:
            raise ValueError("verified receipt requires distinct before and after snapshots")
        aware(self.completed_at, "completed_at")
        for name in ("operation_ids", "verifier_run_ids", "evidence_ids", "changed_paths"):
            values = getattr(self, name)
            if not values:
                raise ValueError(f"{name} must not be empty")
            texts(values, name)
        texts(self.tool_run_ids, "tool_run_ids")
        digest(self.before_tree_sha256, "before_tree_sha256", required=True)
        digest(self.after_tree_sha256, "after_tree_sha256", required=True)
        if self.before_tree_sha256 == self.after_tree_sha256:
            raise ValueError("verified receipt must prove a changed workspace tree")
        _identity(self.result_kind, EngineeringResultKind.VERIFIED_CHANGESET_RECEIPT)
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class EngineeringPublicationProposal:
    proposal_id: str
    task_id: str
    created_at: datetime
    target_kind: str
    remote: str
    source_ref: str
    target_ref: str
    artifact_sha256: tuple[str, ...]
    summary: str
    checkpoint_id: str
    required_authorities: tuple[EngineeringAuthority, ...]
    result_kind: EngineeringResultKind = EngineeringResultKind.PUBLICATION_PROPOSAL
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "proposal_id", "task_id", "target_kind", "remote", "source_ref",
            "target_ref", "summary", "checkpoint_id",
        ):
            text(getattr(self, name), name)
        aware(self.created_at, "created_at")
        if not self.artifact_sha256:
            raise ValueError("publication proposal requires artifact digests")
        for value in self.artifact_sha256:
            digest(value, "artifact_sha256 item", required=True)
        if len(set(self.artifact_sha256)) != len(self.artifact_sha256):
            raise ValueError("artifact_sha256 must not contain duplicates")
        unique_enum(self.required_authorities, "required_authorities")
        if EngineeringAuthority.PUBLISH not in self.required_authorities:
            raise ValueError("publication proposal requires publish authority")
        _identity(self.result_kind, EngineeringResultKind.PUBLICATION_PROPOSAL)
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class EngineeringPublicationReceipt:
    receipt_id: str
    task_id: str
    publication_proposal_id: str
    checkpoint_decision_id: str
    published_at: datetime
    external_reference: str
    observed_remote_revision: str
    evidence_ids: tuple[str, ...]
    verifier_run_ids: tuple[str, ...]
    result_kind: EngineeringResultKind = EngineeringResultKind.PUBLICATION_RECEIPT
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "receipt_id", "task_id", "publication_proposal_id",
            "checkpoint_decision_id", "external_reference",
            "observed_remote_revision",
        ):
            text(getattr(self, name), name)
        aware(self.published_at, "published_at")
        if not self.evidence_ids or not self.verifier_run_ids:
            raise ValueError("publication receipt requires evidence and postcondition verification")
        texts(self.evidence_ids, "evidence_ids")
        texts(self.verifier_run_ids, "verifier_run_ids")
        _identity(self.result_kind, EngineeringResultKind.PUBLICATION_RECEIPT)
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class EngineeringCapabilityUnavailable:
    result_id: str
    task_id: str
    recorded_at: datetime
    capability_id: str
    required_authorities: tuple[EngineeringAuthority, ...]
    reason_code: str
    safe_message: str
    retryable_after_owner_action: bool
    result_kind: EngineeringResultKind = EngineeringResultKind.CAPABILITY_UNAVAILABLE
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("result_id", "task_id", "capability_id", "reason_code", "safe_message"):
            text(getattr(self, name), name)
        aware(self.recorded_at, "recorded_at")
        unique_enum(self.required_authorities, "required_authorities")
        _identity(self.result_kind, EngineeringResultKind.CAPABILITY_UNAVAILABLE)
        _version(self.contract_version)


def _identity(actual: EngineeringResultKind, expected: EngineeringResultKind) -> None:
    if actual is not expected:
        raise ValueError(f"result_kind must be {expected.value}")


def _version(value: str) -> None:
    if value != ENGINEERING_CONTRACT_VERSION:
        raise ValueError("engineering result contract version is unsupported")
