"""Representative database engineering schema values."""

from datetime import datetime, timezone

from fam_os.core.engineering import (
    DatabaseBackupReceipt,
    DatabaseChangePlan,
    DatabaseChangeStatus,
    DatabaseConsistencyMode,
    DatabaseEngine,
    DatabaseEnvironment,
    DatabaseExecutionPermit,
    DatabaseFixtureSet,
    DatabaseMigrationStep,
    DatabaseTarget,
    DatabaseVerificationReceipt,
    DatabasePostapplyReceipt,
    PostgreSQLIntegrationVerificationPlan,
    PostgreSQLIntegrationVerificationReceipt,
    PostgreSQLMigrationAsset,
    EngineeringAuthority,
    EngineeringResourceImpact,
)


NOW = datetime(2026, 7, 19, 16, 0, tzinfo=timezone.utc)
A = "a" * 64
B = "b" * 64
C = "c" * 64


def database_engineering_schema_values() -> tuple[object, ...]:
    target = DatabaseTarget(
        "database-1", DatabaseEngine.SQLITE, DatabaseEnvironment.CANDIDATE,
        "fixture.db", None, "candidate-host-1", False,
    )
    migration = DatabaseMigrationStep(
        "migration-1", 1, "db/001_forward.sql", A,
        "db/001_rollback.sql", B, True, True, C,
    )
    fixtures = DatabaseFixtureSet(
        "fixtures-1", "db/fixtures.json", A, 3, True, False,
    )
    plan = DatabaseChangePlan(
        "database-plan-1", "task-1", "candidate-1", target, A, B,
        (migration,), fixtures, True, True,
        ("schema-match", "foreign-keys", "transaction-test"),
        (EngineeringAuthority.EXECUTE, EngineeringAuthority.MODIFY),
        EngineeringResourceImpact(300, 1, 0, 4, 16_777_216, 0),
        "changeset-1", NOW,
    )
    permit = DatabaseExecutionPermit(
        "database-permit-1", plan.approved_changeset_id,
        target.exact_host_id, NOW, datetime(2026, 7, 19, 17, 0, tzinfo=timezone.utc),
    )
    backup = DatabaseBackupReceipt(
        "backup-1", plan.plan_id, target.target_id,
        DatabaseConsistencyMode.TRANSACTION_SNAPSHOT, C, 4096, A, B, True, NOW,
    )
    receipt = DatabaseVerificationReceipt(
        "database-receipt-1", plan.plan_id, target.target_id, permit.permit_id,
        backup.backup_id,
        DatabaseChangeStatus.VERIFIED, (migration.step_id,), C, C,
        ("transaction-test-1",), "restore-test-1",
        plan.postcondition_ids, None, NOW,
    )
    return target, plan, permit, backup, receipt


def postgresql_integration_verification_schema_values() -> tuple[object, ...]:
    postgres_asset = PostgreSQLMigrationAsset(
        "postgresql-migration-1", 1, "db/001.up.sql", A,
        "db/001.down.sql", B, False,
    )
    postgres_plan = PostgreSQLIntegrationVerificationPlan(
        "postgresql-plan-1", "task-1", "candidate-1", "environment-1",
        "postgresql-candidate", "changeset-1", "candidate-host-1",
        "secret.postgresql", "fam_candidate", "fam_migrator",
        (postgres_asset,), 1_048_576, 16_777_216,
        EngineeringResourceImpact(600, 33, 1, 3, 17_825_792, 0),
        True, True, False,
        NOW, datetime(2026, 7, 19, 17, 0, tzinfo=timezone.utc),
    )
    postgres_receipt = PostgreSQLIntegrationVerificationReceipt(
        receipt_id="postgresql-receipt-1",
        plan_id=postgres_plan.plan_id,
        task_id=postgres_plan.task_id,
        candidate_id=postgres_plan.candidate_id,
        environment_id=postgres_plan.environment_id,
        service_id=postgres_plan.service_id,
        runtime_id="runtime-1",
        permit_id="permit-1",
        authorization_decision_ids=("decision-1",),
        backup_relative_path=".fam/database/backups/postgresql.enc",
        backup_artifact_sha256=C,
        backup_size_bytes=4096,
        backup_encrypted=True,
        baseline_schema_sha256=A,
        baseline_data_sha256=B,
        forward_schema_sha256=C,
        forward_data_sha256=C,
        transaction_schema_sha256=C,
        transaction_data_sha256=C,
        rollback_schema_sha256=A,
        rollback_data_sha256=B,
        reapplied_schema_sha256=C,
        reapplied_data_sha256=C,
        restored_schema_sha256=A,
        restored_data_sha256=B,
        applied_asset_ids=(postgres_asset.asset_id,),
        transaction_test_id="transaction-1",
        passed=True,
        completed_at=NOW,
    )
    return postgres_plan, postgres_receipt


def database_postapply_schema_values() -> tuple[object, ...]:
    target, plan, _permit, _backup, receipt = database_engineering_schema_values()
    return (DatabasePostapplyReceipt(
        "database-postapply-1", plan.task_id, plan.plan_id, target.target_id,
        plan.approved_changeset_id, receipt.receipt_id,
        receipt.schema_sha256, receipt.data_sha256, True, True, True, NOW,
    ),)
