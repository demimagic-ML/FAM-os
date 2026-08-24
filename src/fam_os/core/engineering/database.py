"""Typed database engineering plans, evidence, and rollback contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import (
    aware,
    digest,
    positive,
    relative_path,
    text,
    texts,
)
from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.grants import EngineeringResourceImpact
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class DatabaseEngine(StrEnum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


class DatabaseEnvironment(StrEnum):
    CANDIDATE = "candidate"
    INTEGRATION = "integration"
    STAGING = "staging"
    PRODUCTION = "production"


class DatabaseChangeStatus(StrEnum):
    PLANNED = "planned"
    APPLIED = "applied"
    VERIFIED = "verified"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    RECOVERY_REQUIRED = "recovery_required"


class DatabaseConsistencyMode(StrEnum):
    TRANSACTION_SNAPSHOT = "transaction_snapshot"
    ENGINE_NATIVE_ONLINE = "engine_native_online"
    QUIESCED_OFFLINE = "quiesced_offline"


@dataclass(frozen=True, slots=True)
class DatabaseTarget:
    target_id: str
    engine: DatabaseEngine
    environment: DatabaseEnvironment
    database_name: str
    connection_secret_ref: str | None
    exact_host_id: str
    production: bool
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("target_id", "database_name", "exact_host_id"):
            text(getattr(self, name), name)
        if self.engine is DatabaseEngine.SQLITE:
            relative_path(self.database_name, "database_name")
            if self.connection_secret_ref is not None:
                raise ValueError("candidate SQLite targets cannot consume connection secrets")
            if self.environment is not DatabaseEnvironment.CANDIDATE:
                raise ValueError("SQLite engineering targets are candidate-only")
        elif self.connection_secret_ref is None:
            raise ValueError("remote database targets require an opaque connection secret")
        else:
            text(self.connection_secret_ref, "connection_secret_ref")
        if self.production != (self.environment is DatabaseEnvironment.PRODUCTION):
            raise ValueError("database production flag must match its environment")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("database target contract version is unsupported")


@dataclass(frozen=True, slots=True)
class DatabaseMigrationStep:
    step_id: str
    order: int
    forward_path: str
    forward_sha256: str
    rollback_path: str
    rollback_sha256: str
    destructive: bool
    transaction_safe: bool
    expected_schema_sha256: str

    def __post_init__(self) -> None:
        text(self.step_id, "step_id")
        positive(self.order, "order")
        for name in ("forward_path", "rollback_path"):
            relative_path(getattr(self, name), name)
        for name in (
            "forward_sha256", "rollback_sha256", "expected_schema_sha256",
        ):
            digest(getattr(self, name), name, required=True)


@dataclass(frozen=True, slots=True)
class DatabaseFixtureSet:
    fixture_id: str
    manifest_path: str
    manifest_sha256: str
    row_count: int
    synthetic_only: bool
    contains_secret_content: bool

    def __post_init__(self) -> None:
        text(self.fixture_id, "fixture_id")
        relative_path(self.manifest_path, "manifest_path")
        digest(self.manifest_sha256, "manifest_sha256", required=True)
        positive(self.row_count, "row_count", allow_zero=True)
        if not self.synthetic_only or self.contains_secret_content:
            raise ValueError("database fixtures must be synthetic and secret-free")


@dataclass(frozen=True, slots=True)
class DatabaseChangePlan:
    plan_id: str
    task_id: str
    candidate_id: str
    target: DatabaseTarget
    baseline_schema_sha256: str
    baseline_data_sha256: str
    migration_steps: tuple[DatabaseMigrationStep, ...]
    fixture_set: DatabaseFixtureSet | None
    backup_required: bool
    rollback_required: bool
    postcondition_ids: tuple[str, ...]
    required_authorities: tuple[EngineeringAuthority, ...]
    execution_resource_impact: EngineeringResourceImpact
    approved_changeset_id: str
    created_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("plan_id", "task_id", "candidate_id", "approved_changeset_id"):
            text(getattr(self, name), name)
        for name in ("baseline_schema_sha256", "baseline_data_sha256"):
            digest(getattr(self, name), name, required=True)
        orders = tuple(item.order for item in self.migration_steps)
        if not orders or orders != tuple(range(1, len(orders) + 1)):
            raise ValueError("database migration steps must be contiguous from one")
        if len({item.step_id for item in self.migration_steps}) != len(self.migration_steps):
            raise ValueError("database migration step identities must be unique")
        texts(self.postcondition_ids, "postcondition_ids")
        if EngineeringAuthority.EXECUTE not in self.required_authorities:
            raise ValueError("database plans require execute authority")
        if EngineeringAuthority.MODIFY not in self.required_authorities:
            raise ValueError("database plans require modify authority")
        if (
            self.execution_resource_impact.max_network_bytes != 0
            or self.execution_resource_impact.max_processes != 0
            or self.execution_resource_impact.max_tool_runs != 1
            or self.execution_resource_impact.max_changed_files < 1
            or self.execution_resource_impact.max_changed_bytes < 1
        ):
            raise ValueError("candidate database resource impact is invalid")
        if self.target.production and EngineeringAuthority.PRODUCTION_MUTATE not in self.required_authorities:
            raise ValueError("production database plans require production mutation authority")
        if any(item.destructive for item in self.migration_steps) and not self.backup_required:
            raise ValueError("destructive database plans require a backup")
        if not self.rollback_required:
            raise ValueError("database plans require an explicit rollback lifecycle")
        aware(self.created_at, "created_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("database change plan contract version is unsupported")


@dataclass(frozen=True, slots=True)
class DatabaseBackupReceipt:
    backup_id: str
    plan_id: str
    target_id: str
    consistency_mode: DatabaseConsistencyMode
    artifact_sha256: str
    size_bytes: int
    source_schema_sha256: str
    source_data_sha256: str
    encrypted: bool
    created_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("backup_id", "plan_id", "target_id"):
            text(getattr(self, name), name)
        for name in (
            "artifact_sha256", "source_schema_sha256", "source_data_sha256",
        ):
            digest(getattr(self, name), name, required=True)
        positive(self.size_bytes, "size_bytes")
        if not self.encrypted:
            raise ValueError("database backups must be encrypted before retention")
        aware(self.created_at, "created_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("database backup receipt version is unsupported")


@dataclass(frozen=True, slots=True)
class DatabaseVerificationReceipt:
    receipt_id: str
    plan_id: str
    target_id: str
    execution_permit_id: str
    backup_id: str | None
    status: DatabaseChangeStatus
    applied_step_ids: tuple[str, ...]
    schema_sha256: str
    data_sha256: str
    transaction_test_ids: tuple[str, ...]
    restore_test_id: str
    postcondition_ids: tuple[str, ...]
    rollback_receipt_id: str | None
    completed_at: datetime
    diagnostic: str = ""
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "receipt_id", "plan_id", "target_id", "execution_permit_id",
            "restore_test_id",
        ):
            text(getattr(self, name), name)
        if self.backup_id is not None:
            text(self.backup_id, "backup_id")
        texts(self.applied_step_ids, "applied_step_ids")
        texts(self.transaction_test_ids, "transaction_test_ids")
        texts(self.postcondition_ids, "postcondition_ids")
        digest(self.schema_sha256, "schema_sha256", required=True)
        digest(self.data_sha256, "data_sha256", required=True)
        if self.status is DatabaseChangeStatus.VERIFIED and (
            not self.applied_step_ids
            or not self.transaction_test_ids
            or not self.postcondition_ids
        ):
            raise ValueError("verified database receipts require complete evidence")
        if self.status is DatabaseChangeStatus.ROLLED_BACK and self.rollback_receipt_id is None:
            raise ValueError("rolled-back database receipts require rollback evidence")
        aware(self.completed_at, "completed_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("database verification receipt version is unsupported")


@dataclass(frozen=True, slots=True)
class DatabasePostapplyReceipt:
    receipt_id: str
    task_id: str
    plan_id: str
    target_id: str
    changeset_id: str
    verification_receipt_id: str
    schema_sha256: str
    data_sha256: str
    integrity_ok: bool
    matches_verified_state: bool
    passed: bool
    observed_at: datetime
    diagnostic: str = ""
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "receipt_id", "task_id", "plan_id", "target_id", "changeset_id",
            "verification_receipt_id",
        ):
            text(getattr(self, name), name)
        digest(self.schema_sha256, "schema_sha256", required=True)
        digest(self.data_sha256, "data_sha256", required=True)
        if self.passed and not (self.integrity_ok and self.matches_verified_state):
            raise ValueError("passing database post-apply evidence must be exact")
        if len(self.diagnostic.encode("utf-8")) > 4096:
            raise ValueError("database post-apply diagnostic exceeds its bound")
        aware(self.observed_at, "observed_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("database post-apply receipt version is unsupported")
