"""Fail-closed installed engineering security and soak qualification."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, digest, positive, text, texts
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


ADVERSARIAL_CATEGORIES = frozenset({
    "repository_prompt_injection", "malicious_build_file",
    "package_name_confusion", "compromised_registry", "symlink_race",
    "hardlink_race", "archive_traversal", "fork_bomb", "output_flood",
    "secret_discovery", "data_exfiltration", "malicious_svg_media",
    "git_hook_execution", "submodule_escape", "stale_approval",
    "restart_replay",
})


class EngineeringQualificationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class EngineeringSecurityReview:
    review_id: str
    release_id: str
    reviewer_id: str
    reviewer_independent: bool
    reviewed_areas: tuple[str, ...]
    finding_ids: tuple[str, ...]
    blocking_finding_ids: tuple[str, ...]
    review_document_sha256: str
    reviewer_signature_sha256: str
    completed_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("review_id", "release_id", "reviewer_id"):
            text(getattr(self, name), name)
        texts(self.reviewed_areas, "reviewed areas")
        texts(self.finding_ids, "finding IDs")
        texts(self.blocking_finding_ids, "blocking finding IDs")
        digest(self.review_document_sha256, "review_document_sha256", required=True)
        digest(self.reviewer_signature_sha256, "reviewer_signature_sha256", required=True)
        aware(self.completed_at, "completed_at")
        required = {
            "command_execution", "dependency_network_authority",
            "creative_file_parsers", "git_credentials",
            "remote_publication", "self_modification",
        }
        if not self.reviewer_independent or not required.issubset(self.reviewed_areas):
            raise ValueError("engineering security review must be independent and complete")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering security review contract version is unsupported")


@dataclass(frozen=True, slots=True)
class EngineeringPressureSoakReport:
    report_id: str
    release_id: str
    started_at: datetime
    completed_at: datetime
    duration_seconds: int
    task_count: int
    interruption_count: int
    rollback_count: int
    model_eviction_count: int
    compiler_workload_count: int
    dependency_failure_count: int
    candidate_cleanup_count: int
    leaked_candidate_count: int
    failed_task_count: int
    raw_evidence_sha256: str
    status: EngineeringQualificationStatus
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.report_id, "report_id")
        text(self.release_id, "release_id")
        aware(self.started_at, "started_at")
        aware(self.completed_at, "completed_at")
        positive(self.duration_seconds, "duration_seconds")
        for name in (
            "task_count", "interruption_count", "rollback_count",
            "model_eviction_count", "compiler_workload_count",
            "dependency_failure_count", "candidate_cleanup_count",
            "leaked_candidate_count", "failed_task_count",
        ):
            positive(getattr(self, name), name, allow_zero=True)
        digest(self.raw_evidence_sha256, "raw_evidence_sha256", required=True)
        if self.status is EngineeringQualificationStatus.PASSED and (
            self.duration_seconds < 86_400 or self.leaked_candidate_count
        ):
            raise ValueError("passing engineering soak requires 24 hours and zero leaked candidates")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering soak contract version is unsupported")


@dataclass(frozen=True, slots=True)
class InstalledEngineeringQualification:
    qualification_id: str
    release_id: str
    hardware_profile_ids: tuple[str, ...]
    dependency_profile_ids: tuple[str, ...]
    language_qualification_ids: tuple[str, ...]
    installed_scenario_ids: tuple[str, ...]
    adversarial_evidence: tuple[tuple[str, str], ...]
    soak_report_id: str | None
    independent_review_id: str | None
    coverage_manifest_sha256: str | None
    status: EngineeringQualificationStatus
    qualified_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.qualification_id, "qualification_id")
        text(self.release_id, "release_id")
        for values, name in (
            (self.hardware_profile_ids, "hardware profile IDs"),
            (self.dependency_profile_ids, "dependency profile IDs"),
            (self.language_qualification_ids, "language qualification IDs"),
            (self.installed_scenario_ids, "installed scenario IDs"),
        ):
            texts(values, name)
        categories = {category for category, _evidence in self.adversarial_evidence}
        for _category, evidence in self.adversarial_evidence:
            text(evidence, "adversarial evidence ID")
        if self.status is EngineeringQualificationStatus.PASSED:
            if set(self.hardware_profile_ids) != {"compat-cpu-16gb", "full-reference-workstation"}:
                raise ValueError("passing engineering qualification requires both hardware profiles")
            if not ADVERSARIAL_CATEGORIES.issubset(categories):
                raise ValueError("passing engineering qualification lacks adversarial categories")
            if not self.soak_report_id or not self.independent_review_id or not self.coverage_manifest_sha256:
                raise ValueError("passing engineering qualification requires soak review and installed coverage")
        digest(self.coverage_manifest_sha256, "coverage_manifest_sha256")
        aware(self.qualified_at, "qualified_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("installed engineering qualification contract version is unsupported")
