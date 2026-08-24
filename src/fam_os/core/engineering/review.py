"""Independent engineering review checkpoints and attributable findings."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import base64
import hashlib
import json

from fam_os.core.engineering._validation import aware, digest, relative_path, text, texts
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class EngineeringReviewDiscipline(StrEnum):
    CODE = "code"
    SECURITY = "security"
    ARCHITECTURE = "architecture"
    DESIGN = "design"


class EngineeringFindingSeverity(StrEnum):
    INFORMATION = "information"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EngineeringFindingDisposition(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    WAIVED = "waived"


class EngineeringReviewStatus(StrEnum):
    BLOCKED = "blocked"
    PASSED = "passed"
    WAIVED = "waived"


@dataclass(frozen=True, slots=True)
class EngineeringReviewSelection:
    selection_id: str
    task_id: str
    candidate_id: str
    changeset_sha256: str
    policy_id: str
    intent_sha256: str
    required_disciplines: tuple[EngineeringReviewDiscipline, ...]
    selected_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "selection_id", "task_id", "candidate_id", "policy_id",
        ):
            text(getattr(self, name), name)
        digest(self.changeset_sha256, "changeset_sha256", required=True)
        digest(self.intent_sha256, "intent_sha256", required=True)
        if (
            not self.required_disciplines
            or len(self.required_disciplines)
            != len(set(self.required_disciplines))
        ):
            raise ValueError("engineering review selection disciplines are invalid")
        aware(self.selected_at, "selected_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering review selection version is unsupported")


@dataclass(frozen=True, slots=True)
class SignedEngineeringReviewerRecipe:
    recipe_id: str
    recipe_version: str
    reviewer_id: str
    adapter_id: str
    disciplines: tuple[EngineeringReviewDiscipline, ...]
    signer_key_id: str
    payload_sha256: str
    signature_base64: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "recipe_id", "recipe_version", "reviewer_id", "adapter_id",
            "signer_key_id", "signature_base64",
        ):
            text(getattr(self, name), name)
        if (
            not self.disciplines
            or len(self.disciplines) != len(set(self.disciplines))
        ):
            raise ValueError("signed reviewer disciplines are invalid")
        digest(self.payload_sha256, "payload_sha256", required=True)
        try:
            signature = base64.b64decode(self.signature_base64, validate=True)
        except (TypeError, ValueError) as error:
            raise ValueError("reviewer recipe signature must be strict base64") from error
        if len(signature) != 64:
            raise ValueError("reviewer recipe signature must be Ed25519")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("signed reviewer recipe version is unsupported")

    @property
    def coordinate(self) -> str:
        return f"{self.recipe_id}@{self.recipe_version}"


@dataclass(frozen=True, slots=True)
class EngineeringReviewResolutionReceipt:
    receipt_id: str
    task_id: str
    candidate_id: str
    changeset_sha256: str
    checkpoint_id: str
    finding_id: str
    remediation_evidence_ids: tuple[str, ...]
    verification_evidence_ids: tuple[str, ...]
    reviewer_id: str
    reviewer_independence_ref: str
    resolved_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "receipt_id", "task_id", "candidate_id", "checkpoint_id",
            "finding_id", "reviewer_id", "reviewer_independence_ref",
        ):
            text(getattr(self, name), name)
        digest(self.changeset_sha256, "changeset_sha256", required=True)
        if not self.remediation_evidence_ids or not self.verification_evidence_ids:
            raise ValueError("review resolution requires remediation and verification evidence")
        texts(self.remediation_evidence_ids, "remediation_evidence_ids")
        texts(self.verification_evidence_ids, "verification_evidence_ids")
        aware(self.resolved_at, "resolved_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering review resolution version is unsupported")


@dataclass(frozen=True, slots=True)
class EngineeringReviewWaiverDecision:
    decision_id: str
    checkpoint_id: str
    finding_id: str
    owner_id: str
    authentication_context_id: str
    consequences_sha256: str
    truthful_assurance: str
    decided_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "decision_id", "checkpoint_id", "finding_id", "owner_id",
            "authentication_context_id", "truthful_assurance",
        ):
            text(getattr(self, name), name)
        digest(self.consequences_sha256, "consequences_sha256", required=True)
        if self.truthful_assurance not in {"review_waived", "partially_reviewed"}:
            raise ValueError("review waiver assurance must remain truthful")
        aware(self.decided_at, "decided_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering review waiver version is unsupported")


@dataclass(frozen=True, slots=True)
class EngineeringReviewFinding:
    finding_id: str
    discipline: EngineeringReviewDiscipline
    severity: EngineeringFindingSeverity
    title: str
    path: str | None
    evidence_ids: tuple[str, ...]
    disposition: EngineeringFindingDisposition
    resolution_receipt_id: str | None = None
    waiver_decision_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("finding_id", "title"):
            text(getattr(self, name), name)
        if self.path is not None:
            relative_path(self.path, "review finding path")
        if not self.evidence_ids:
            raise ValueError("engineering review finding requires evidence")
        texts(self.evidence_ids, "evidence_ids")
        expected = {
            EngineeringFindingDisposition.OPEN: (False, False),
            EngineeringFindingDisposition.RESOLVED: (True, False),
            EngineeringFindingDisposition.WAIVED: (False, True),
        }[self.disposition]
        if expected != (
            self.resolution_receipt_id is not None,
            self.waiver_decision_id is not None,
        ):
            raise ValueError("engineering finding disposition evidence is inconsistent")


@dataclass(frozen=True, slots=True)
class EngineeringReviewCheckpoint:
    checkpoint_id: str
    task_id: str
    candidate_id: str
    changeset_sha256: str
    producer_id: str
    reviewer_id: str
    reviewer_independence_ref: str
    required_disciplines: tuple[EngineeringReviewDiscipline, ...]
    findings: tuple[EngineeringReviewFinding, ...]
    status: EngineeringReviewStatus
    completed_at: datetime
    revision: int = 0
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "checkpoint_id", "task_id", "candidate_id", "producer_id",
            "reviewer_id", "reviewer_independence_ref",
        ):
            text(getattr(self, name), name)
        digest(self.changeset_sha256, "changeset_sha256", required=True)
        if self.producer_id == self.reviewer_id:
            raise ValueError("engineering review must be independent")
        if not self.required_disciplines or len(set(self.required_disciplines)) != len(self.required_disciplines):
            raise ValueError("engineering review disciplines are invalid")
        if any(item.discipline not in self.required_disciplines for item in self.findings):
            raise ValueError("engineering finding discipline was not selected")
        _validate_status(self.status, self.findings)
        aware(self.completed_at, "completed_at")
        if self.revision < 0:
            raise ValueError("engineering review revision is invalid")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering review version is unsupported")


def _validate_status(status, findings) -> None:
    open_findings = [item for item in findings if item.disposition is EngineeringFindingDisposition.OPEN]
    waived = [item for item in findings if item.disposition is EngineeringFindingDisposition.WAIVED]
    expected = (
        EngineeringReviewStatus.BLOCKED if open_findings
        else EngineeringReviewStatus.WAIVED if waived
        else EngineeringReviewStatus.PASSED
    )
    if status is not expected:
        raise ValueError("engineering review status does not match its findings")


def review_waiver_consequences_digest(checkpoint, finding) -> str:
    payload = {
        "checkpoint_id": checkpoint.checkpoint_id,
        "task_id": checkpoint.task_id,
        "candidate_id": checkpoint.candidate_id,
        "changeset_sha256": checkpoint.changeset_sha256,
        "finding_id": finding.finding_id,
        "discipline": finding.discipline.value,
        "severity": finding.severity.value,
        "title": finding.title,
        "evidence_ids": list(finding.evidence_ids),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
