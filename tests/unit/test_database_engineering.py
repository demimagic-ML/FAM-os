import unittest
from dataclasses import replace

from fam_os.core.engineering import (
    DatabaseEngine,
    DatabaseChangeStatus,
    DatabaseEnvironment,
    EngineeringAuthority,
)
from tests.contract.schema_database_engineering_fixtures import (
    database_engineering_schema_values,
)


class DatabaseEngineeringContractTests(unittest.TestCase):
    def test_candidate_sqlite_is_relative_and_secret_free(self) -> None:
        target, _plan, _permit, _backup, _receipt = database_engineering_schema_values()
        with self.assertRaisesRegex(ValueError, "cannot consume"):
            replace(target, connection_secret_ref="secret.database")
        with self.assertRaisesRegex(ValueError, "relative"):
            replace(target, database_name="/host/database.sqlite")
        with self.assertRaisesRegex(ValueError, "opaque connection secret"):
            replace(target, engine=DatabaseEngine.POSTGRESQL)

    def test_destructive_plan_requires_backup_and_rollback(self) -> None:
        _target, plan, _permit, _backup, _receipt = database_engineering_schema_values()
        with self.assertRaisesRegex(ValueError, "require a backup"):
            replace(plan, backup_required=False)
        with self.assertRaisesRegex(ValueError, "rollback lifecycle"):
            replace(plan, rollback_required=False)

    def test_production_target_requires_exact_production_authority(self) -> None:
        target, plan, _permit, _backup, _receipt = database_engineering_schema_values()
        production = replace(
            target, engine=DatabaseEngine.POSTGRESQL,
            environment=DatabaseEnvironment.PRODUCTION, production=True,
            connection_secret_ref="secret.database-production",
        )
        with self.assertRaisesRegex(ValueError, "production mutation"):
            replace(plan, target=production)
        admitted = replace(
            plan, target=production,
            required_authorities=(
                EngineeringAuthority.EXECUTE,
                EngineeringAuthority.MODIFY,
                EngineeringAuthority.PRODUCTION_MUTATE,
            ),
        )
        self.assertTrue(admitted.target.production)

    def test_verified_receipt_requires_tests_and_postconditions(self) -> None:
        _target, _plan, _permit, _backup, receipt = database_engineering_schema_values()
        with self.assertRaisesRegex(ValueError, "complete evidence"):
            replace(receipt, transaction_test_ids=())
        with self.assertRaisesRegex(ValueError, "rollback evidence"):
            replace(
                receipt, status=DatabaseChangeStatus.ROLLED_BACK,
                rollback_receipt_id=None,
            )


if __name__ == "__main__":
    unittest.main()
