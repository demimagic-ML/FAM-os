"""Evidence emitted by bounded integration environments."""

from dataclasses import dataclass
from datetime import datetime

from fam_os.core.engineering._validation import (
    aware, digest, relative_path, text, texts,
)
from fam_os.core.engineering.integration_environment import (
    IntegrationEnvironmentStatus,
    IntegrationExecutionPermit,
)
from fam_os.core.engineering.integration_network import IntegrationNetworkUsage
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class IntegrationAllocatedPort:
    name: str
    host_port: int

    def __post_init__(self) -> None:
        text(self.name, "allocated port name")
        if isinstance(self.host_port, bool) or not 1 <= self.host_port <= 65535:
            raise ValueError("allocated integration port is invalid")


@dataclass(frozen=True, slots=True)
class IntegrationRetainedArtifact:
    relative_path: str
    sha256: str

    def __post_init__(self) -> None:
        relative_path(self.relative_path, "retained artifact path")
        digest(self.sha256, "retained artifact digest", required=True)


@dataclass(frozen=True, slots=True)
class IntegrationServiceReceipt:
    service_id: str
    runtime_id: str
    image_sha256: str | None
    allocated_ports: tuple[IntegrationAllocatedPort, ...]
    health_evidence_id: str
    exit_code: int | None

    def __post_init__(self) -> None:
        for name in ("service_id", "runtime_id", "health_evidence_id"):
            text(getattr(self, name), name)
        digest(self.image_sha256, "image_sha256")
        names = tuple(item.name for item in self.allocated_ports)
        texts(names, "allocated port names")
        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise ValueError("integration service exit code is invalid")


@dataclass(frozen=True, slots=True)
class IntegrationEnvironmentReceipt:
    receipt_id: str
    environment_id: str
    permit_id: str
    status: IntegrationEnvironmentStatus
    started_at: datetime
    completed_at: datetime
    services: tuple[IntegrationServiceReceipt, ...]
    retained_artifacts: tuple[IntegrationRetainedArtifact, ...]
    cleanup_evidence_ids: tuple[str, ...]
    network_usage: IntegrationNetworkUsage | None = None
    diagnostic: str = ""
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("receipt_id", "environment_id", "permit_id"):
            text(getattr(self, name), name)
        aware(self.started_at, "started_at")
        aware(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("integration receipt completion predates start")
        if not isinstance(self.status, IntegrationEnvironmentStatus):
            raise ValueError("integration environment status is invalid")
        identities = tuple(item.service_id for item in self.services)
        if len(set(identities)) != len(identities):
            raise ValueError("service receipt identities must be unique")
        paths = tuple(item.relative_path for item in self.retained_artifacts)
        texts(paths, "retained artifact paths")
        texts(self.cleanup_evidence_ids, "cleanup_evidence_ids")
        if self.network_usage is not None and not isinstance(
            self.network_usage, IntegrationNetworkUsage,
        ):
            raise ValueError("integration network usage is invalid")
        if self.status is IntegrationEnvironmentStatus.READY and not self.services:
            raise ValueError("ready integration receipt requires services")
        if self.status is IntegrationEnvironmentStatus.CLEANED and not self.cleanup_evidence_ids:
            raise ValueError("cleaned integration receipt requires cleanup evidence")
        if self.status is IntegrationEnvironmentStatus.FAILED and not self.diagnostic.strip():
            raise ValueError("failed integration receipt requires a diagnostic")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("integration environment receipt version is unsupported")


@dataclass(frozen=True, slots=True)
class IntegrationEnvironmentStartResult:
    environment_id: str
    plan_sha256: str
    permit: IntegrationExecutionPermit
    receipt: IntegrationEnvironmentReceipt
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.environment_id, "environment_id")
        digest(self.plan_sha256, "plan_sha256", required=True)
        if (
            self.permit.environment_id != self.environment_id
            or self.receipt.environment_id != self.environment_id
            or self.receipt.permit_id != self.permit.permit_id
        ):
            raise ValueError("integration start result identities do not match")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("integration start result version is unsupported")
