"""Typed candidate-only PostgreSQL migration verification contracts."""

from dataclasses import dataclass
from datetime import datetime

from fam_os.core.engineering._validation import (
    aware,
    digest,
    positive,
    relative_path,
    text,
    texts,
)
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION
from fam_os.core.engineering.grants import EngineeringResourceImpact


POSTGRESQL_CANDIDATE_DATABASE = "fam_candidate"
POSTGRESQL_MIGRATION_ROLE = "fam_migrator"


@dataclass(frozen=True, slots=True)
class PostgreSQLMigrationAsset:
    """One digest-bound reversible candidate migration pair."""

    asset_id: str
    order: int
    forward_path: str
    forward_sha256: str
    rollback_path: str
    rollback_sha256: str
    destructive: bool

    def __post_init__(self) -> None:
        text(self.asset_id, "PostgreSQL migration asset_id")
        positive(self.order, "PostgreSQL migration order")
        for name in ("forward_path", "rollback_path"):
            relative_path(getattr(self, name), name)
        for name in ("forward_sha256", "rollback_sha256"):
            digest(getattr(self, name), name, required=True)
        if self.forward_path == self.rollback_path:
            raise ValueError("PostgreSQL forward and rollback assets must differ")


@dataclass(frozen=True, slots=True)
class PostgreSQLIntegrationVerificationPlan:
    """Exact isolated-service plan; never a remote database mutation plan."""

    plan_id: str
    task_id: str
    candidate_id: str
    environment_id: str
    service_id: str
    approved_changeset_id: str
    exact_host_id: str
    connection_secret_ref: str
    database_name: str
    migration_role: str
    migration_assets: tuple[PostgreSQLMigrationAsset, ...]
    maximum_input_bytes: int
    maximum_backup_bytes: int
    execution_resource_impact: EngineeringResourceImpact
    backup_required: bool
    rollback_required: bool
    production: bool
    created_at: datetime
    expires_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "plan_id", "task_id", "candidate_id", "environment_id",
            "service_id", "approved_changeset_id", "exact_host_id",
            "connection_secret_ref",
        ):
            text(getattr(self, name), name)
        if self.database_name != POSTGRESQL_CANDIDATE_DATABASE:
            raise ValueError("PostgreSQL verification database identity is fixed")
        if self.migration_role != POSTGRESQL_MIGRATION_ROLE:
            raise ValueError("PostgreSQL verification role identity is fixed")
        orders = tuple(item.order for item in self.migration_assets)
        if not orders or orders != tuple(range(1, len(orders) + 1)):
            raise ValueError("PostgreSQL migration assets must be contiguous from one")
        identities = tuple(item.asset_id for item in self.migration_assets)
        texts(identities, "PostgreSQL migration asset identities")
        positive(self.maximum_input_bytes, "maximum_input_bytes")
        if self.maximum_input_bytes > 16 * 1024 * 1024:
            raise ValueError("PostgreSQL verification input bound is too large")
        positive(self.maximum_backup_bytes, "maximum_backup_bytes")
        if self.maximum_backup_bytes > 64 * 1024 * 1024:
            raise ValueError("PostgreSQL verification backup bound is too large")
        if len(self.migration_assets) > 4:
            raise ValueError("PostgreSQL verification has too many migration pairs")
        expected_impact = EngineeringResourceImpact(
            600,
            24 + 9 * len(self.migration_assets),
            1,
            2 * len(self.migration_assets) + 1,
            self.maximum_input_bytes + self.maximum_backup_bytes,
            0,
        )
        if self.execution_resource_impact != expected_impact:
            raise ValueError("PostgreSQL verification resource impact is not exact")
        if not self.backup_required or not self.rollback_required:
            raise ValueError("PostgreSQL verification requires backup and rollback")
        if self.production:
            raise PermissionError("PostgreSQL integration verification is candidate-only")
        aware(self.created_at, "created_at")
        aware(self.expires_at, "expires_at")
        if self.expires_at <= self.created_at:
            raise ValueError("PostgreSQL verification plan must expire")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("PostgreSQL verification plan version is unsupported")


@dataclass(frozen=True, slots=True)
class PostgreSQLIntegrationVerificationReceipt:
    """Backup, forward, rollback, replay, transaction, and restore evidence."""

    receipt_id: str
    plan_id: str
    task_id: str
    candidate_id: str
    environment_id: str
    service_id: str
    runtime_id: str
    permit_id: str
    authorization_decision_ids: tuple[str, ...]
    backup_relative_path: str
    backup_artifact_sha256: str
    backup_size_bytes: int
    backup_encrypted: bool
    baseline_schema_sha256: str
    baseline_data_sha256: str
    forward_schema_sha256: str
    forward_data_sha256: str
    transaction_schema_sha256: str
    transaction_data_sha256: str
    rollback_schema_sha256: str
    rollback_data_sha256: str
    reapplied_schema_sha256: str
    reapplied_data_sha256: str
    restored_schema_sha256: str
    restored_data_sha256: str
    applied_asset_ids: tuple[str, ...]
    transaction_test_id: str
    passed: bool
    completed_at: datetime
    diagnostic: str = ""
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "receipt_id", "plan_id", "task_id", "candidate_id",
            "environment_id", "service_id", "runtime_id", "permit_id",
            "transaction_test_id",
        ):
            text(getattr(self, name), name)
        relative_path(self.backup_relative_path, "backup_relative_path")
        texts(
            self.authorization_decision_ids,
            "PostgreSQL authorization_decision_ids",
        )
        digest(
            self.backup_artifact_sha256,
            "backup_artifact_sha256",
            required=True,
        )
        positive(self.backup_size_bytes, "backup_size_bytes")
        for name in (
            "baseline_schema_sha256", "baseline_data_sha256",
            "forward_schema_sha256", "forward_data_sha256",
            "transaction_schema_sha256", "transaction_data_sha256",
            "rollback_schema_sha256", "rollback_data_sha256",
            "reapplied_schema_sha256", "reapplied_data_sha256",
            "restored_schema_sha256", "restored_data_sha256",
        ):
            digest(getattr(self, name), name, required=True)
        texts(self.applied_asset_ids, "applied_asset_ids")
        if self.passed and not self.backup_encrypted:
            raise ValueError("passing PostgreSQL evidence requires encrypted backup")
        if self.passed and not self.applied_asset_ids:
            raise ValueError("passing PostgreSQL evidence requires applied assets")
        if self.passed and not self.authorization_decision_ids:
            raise ValueError("passing PostgreSQL evidence requires live decisions")
        if self.passed and (
            self.transaction_schema_sha256 != self.forward_schema_sha256
            or self.transaction_data_sha256 != self.forward_data_sha256
            or self.rollback_schema_sha256 != self.baseline_schema_sha256
            or self.rollback_data_sha256 != self.baseline_data_sha256
            or self.reapplied_schema_sha256 != self.forward_schema_sha256
            or self.reapplied_data_sha256 != self.forward_data_sha256
            or self.restored_schema_sha256 != self.baseline_schema_sha256
            or self.restored_data_sha256 != self.baseline_data_sha256
        ):
            raise ValueError("passing PostgreSQL lifecycle evidence is not exact")
        if len(self.diagnostic.encode("utf-8")) > 4096:
            raise ValueError("PostgreSQL verification diagnostic exceeds its bound")
        aware(self.completed_at, "completed_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("PostgreSQL verification receipt version is unsupported")
