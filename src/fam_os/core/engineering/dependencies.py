"""Isolated dependency resolution, SBOM, and supply-chain evidence contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, digest, positive, relative_path, text, texts
from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class DependencyFindingSeverity(StrEnum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DependencyResolutionStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class DependencyResolutionBudget:
    maximum_packages: int
    maximum_download_bytes: int
    maximum_installed_bytes: int
    maximum_wall_seconds: int

    def __post_init__(self) -> None:
        for name in (
            "maximum_packages", "maximum_download_bytes",
            "maximum_installed_bytes", "maximum_wall_seconds",
        ):
            positive(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class DependencyResolutionRequest:
    request_id: str
    task_id: str
    candidate_id: str
    ecosystem: str
    manifest_paths: tuple[str, ...]
    lockfile_paths: tuple[str, ...]
    registry_urls: tuple[str, ...]
    network_hosts: tuple[str, ...]
    allowed_license_expressions: tuple[str, ...]
    budget: DependencyResolutionBudget
    environment_path: str
    approved_at: datetime
    authorities: tuple[EngineeringAuthority, ...]
    requested_packages: tuple[str, ...]
    global_install: bool = False
    host_toolchain_mutation: bool = False
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("request_id", "task_id", "candidate_id", "ecosystem"):
            text(getattr(self, name), name)
        for path in self.manifest_paths + self.lockfile_paths + (self.environment_path,):
            relative_path(path, "dependency path")
        texts(self.manifest_paths, "manifest_paths")
        texts(self.lockfile_paths, "lockfile_paths")
        texts(self.registry_urls, "registry_urls")
        texts(self.network_hosts, "network_hosts")
        texts(self.allowed_license_expressions, "allowed_license_expressions")
        texts(self.requested_packages, "requested_packages")
        aware(self.approved_at, "approved_at")
        required = {EngineeringAuthority.MODIFY, EngineeringAuthority.NETWORK}
        if not required.issubset(self.authorities):
            raise ValueError("dependency resolution requires modify and network authority")
        if not self.registry_urls or not self.network_hosts:
            raise ValueError("dependency resolution requires named registries and hosts")
        if not self.requested_packages:
            raise ValueError("dependency resolution requires exact package names")
        if self.global_install or self.host_toolchain_mutation:
            raise ValueError("project dependency resolution cannot mutate host or global state")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("dependency request contract version is unsupported")


@dataclass(frozen=True, slots=True)
class SbomComponent:
    package_url: str
    name: str
    version: str
    sha256: str
    license_expression: str
    direct: bool

    def __post_init__(self) -> None:
        for name in ("package_url", "name", "version", "license_expression"):
            text(getattr(self, name), name)
        digest(self.sha256, "sha256", required=True)


@dataclass(frozen=True, slots=True)
class DependencyVulnerabilityFinding:
    finding_id: str
    package_url: str
    advisory_id: str
    severity: DependencyFindingSeverity
    affected_version: str
    fixed_version: str | None

    def __post_init__(self) -> None:
        for name in ("finding_id", "package_url", "advisory_id", "affected_version"):
            text(getattr(self, name), name)
        if self.fixed_version is not None:
            text(self.fixed_version, "fixed_version")


@dataclass(frozen=True, slots=True)
class DependencyResolutionReceipt:
    receipt_id: str
    request_id: str
    task_id: str
    candidate_id: str
    started_at: datetime
    completed_at: datetime
    status: DependencyResolutionStatus
    manifest_before_sha256: tuple[str, ...]
    manifest_after_sha256: tuple[str, ...]
    lockfile_before_sha256: tuple[str, ...]
    lockfile_after_sha256: tuple[str, ...]
    components: tuple[SbomComponent, ...]
    vulnerability_findings: tuple[DependencyVulnerabilityFinding, ...]
    license_result_ids: tuple[str, ...]
    network_destinations: tuple[str, ...]
    downloaded_bytes: int
    installed_bytes: int
    environment_path: str
    artifact_digests: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    global_state_unchanged: bool = True
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("receipt_id", "request_id", "task_id", "candidate_id"):
            text(getattr(self, name), name)
        aware(self.started_at, "started_at")
        aware(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("dependency receipt completion cannot predate start")
        for values, name in (
            (self.manifest_before_sha256, "manifest before digest"),
            (self.manifest_after_sha256, "manifest after digest"),
            (self.lockfile_before_sha256, "lockfile before digest"),
            (self.lockfile_after_sha256, "lockfile after digest"),
            (self.artifact_digests, "artifact digest"),
        ):
            for value in values:
                digest(value, name, required=True)
        texts(self.license_result_ids, "license_result_ids")
        texts(self.network_destinations, "network_destinations")
        texts(self.rejection_reasons, "rejection_reasons")
        positive(self.downloaded_bytes, "downloaded_bytes", allow_zero=True)
        positive(self.installed_bytes, "installed_bytes", allow_zero=True)
        relative_path(self.environment_path, "environment_path")
        if not self.global_state_unchanged:
            raise ValueError("project dependency receipt cannot claim global mutation")
        if self.status is DependencyResolutionStatus.ACCEPTED and self.rejection_reasons:
            raise ValueError("accepted dependency receipt cannot carry rejection reasons")
        if self.status is DependencyResolutionStatus.REJECTED and not self.rejection_reasons:
            raise ValueError("rejected dependency receipt requires reasons")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("dependency receipt contract version is unsupported")
