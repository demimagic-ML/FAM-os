"""Host-administration, global-install, and tiered secret-use contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, digest, positive, text, texts
from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class HostAdministrationMechanism(StrEnum):
    SUDO = "sudo"
    POLKIT = "polkit"
    SYSTEMD = "systemd"
    PACKAGE_MANAGER = "package_manager"
    DEVICE = "device"
    FILESYSTEM = "filesystem"


class HostChangeStatus(StrEnum):
    PROPOSED = "proposed"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class SecretUseLevel(StrEnum):
    OPAQUE_INJECTION = "opaque_injection"
    REDACTED_TRANSFORMATION = "redacted_transformation"
    DIRECT_MODEL_DISCLOSURE = "direct_model_disclosure"


@dataclass(frozen=True, slots=True)
class HostAdministrationChangeSet:
    change_set_id: str
    task_id: str
    grant_id: str
    owner_id: str
    mechanism: HostAdministrationMechanism
    package_sources: tuple[str, ...]
    packages: tuple[str, ...]
    predicted_effects: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    before_evidence_ids: tuple[str, ...]
    requested_at: datetime
    interactive_authentication_required: bool = True
    global_install: bool = False
    host_toolchain_change: bool = False
    required_authorities: tuple[EngineeringAuthority, ...] = (
        EngineeringAuthority.HOST_ADMIN,
    )
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("change_set_id", "task_id", "grant_id", "owner_id"):
            text(getattr(self, name), name)
        texts(self.package_sources, "package_sources")
        texts(self.packages, "packages")
        texts(self.predicted_effects, "predicted_effects")
        texts(self.rollback_steps, "rollback_steps")
        texts(self.before_evidence_ids, "before_evidence_ids")
        aware(self.requested_at, "requested_at")
        if not self.interactive_authentication_required:
            raise ValueError("host administration requires interactive owner authentication")
        authorities = set(self.required_authorities)
        if EngineeringAuthority.HOST_ADMIN not in authorities:
            raise ValueError("host change requires host-admin authority")
        if self.global_install or self.host_toolchain_change:
            if EngineeringAuthority.GLOBAL_INSTALL not in authorities:
                raise ValueError("global installation requires its distinct authority")
            if not self.package_sources or not self.packages:
                raise ValueError("global install requires exact sources and packages")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("host change contract version is unsupported")


@dataclass(frozen=True, slots=True)
class HostAdministrationReceipt:
    receipt_id: str
    change_set_id: str
    broker_id: str
    owner_authentication_context_id: str
    status: HostChangeStatus
    started_at: datetime
    completed_at: datetime
    before_evidence_ids: tuple[str, ...]
    after_evidence_ids: tuple[str, ...]
    applied_effects: tuple[str, ...]
    rollback_evidence_ids: tuple[str, ...]
    exit_code: int | None
    audit_sha256: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("receipt_id", "change_set_id", "broker_id", "owner_authentication_context_id"):
            text(getattr(self, name), name)
        aware(self.started_at, "started_at")
        aware(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("host receipt completion cannot predate start")
        texts(self.before_evidence_ids, "before_evidence_ids")
        texts(self.after_evidence_ids, "after_evidence_ids")
        texts(self.applied_effects, "applied_effects")
        texts(self.rollback_evidence_ids, "rollback_evidence_ids")
        digest(self.audit_sha256, "audit_sha256", required=True)
        if self.status is HostChangeStatus.APPLIED and (not self.after_evidence_ids or self.exit_code != 0):
            raise ValueError("applied host change requires successful after evidence")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("host receipt contract version is unsupported")


@dataclass(frozen=True, slots=True)
class SecretUseAuthorization:
    authorization_id: str
    task_id: str
    grant_id: str
    owner_id: str
    principal_id: str
    secret_ref: str
    level: SecretUseLevel
    approved_consumer_id: str
    purpose: str
    issued_at: datetime
    expires_at: datetime
    maximum_uses: int
    direct_disclosure_consequences_sha256: str | None = None
    required_authority: EngineeringAuthority = EngineeringAuthority.SECRET_USE
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("authorization_id", "task_id", "grant_id", "owner_id", "principal_id", "secret_ref", "approved_consumer_id", "purpose"):
            text(getattr(self, name), name)
        aware(self.issued_at, "issued_at")
        aware(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("secret use authorization must expire")
        positive(self.maximum_uses, "maximum_uses")
        digest(self.direct_disclosure_consequences_sha256, "direct_disclosure_consequences_sha256")
        if self.required_authority is not EngineeringAuthority.SECRET_USE:
            raise ValueError("secret use requires its distinct authority")
        direct = self.level is SecretUseLevel.DIRECT_MODEL_DISCLOSURE
        if direct != (self.direct_disclosure_consequences_sha256 is not None):
            raise ValueError("direct model disclosure requires exact consequence approval")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("secret use contract version is unsupported")


@dataclass(frozen=True, slots=True)
class SecretUseReceipt:
    receipt_id: str
    authorization_id: str
    secret_ref: str
    consumer_id: str
    level: SecretUseLevel
    used_at: datetime
    output_sha256: str
    redaction_evidence_id: str | None
    plaintext_persisted: bool = False
    secret_value_logged: bool = False
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("receipt_id", "authorization_id", "secret_ref", "consumer_id"):
            text(getattr(self, name), name)
        aware(self.used_at, "used_at")
        digest(self.output_sha256, "output_sha256", required=True)
        if self.redaction_evidence_id is not None:
            text(self.redaction_evidence_id, "redaction_evidence_id")
        if self.level is SecretUseLevel.REDACTED_TRANSFORMATION and self.redaction_evidence_id is None:
            raise ValueError("redacted secret use requires redaction evidence")
        if self.plaintext_persisted or self.secret_value_logged:
            raise ValueError("secret receipts cannot persist or log plaintext")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("secret receipt contract version is unsupported")
