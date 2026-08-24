import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.database import NaturalPostgreSQLVerificationPlanBuilder
from fam_os.adapters.integration import NaturalIntegrationEnvironmentPlanner
from fam_os.core.engineering import (
    CandidateBaselineEntry,
    CandidateEntryKind,
    CandidateWorkspace,
    NaturalLanguageEngineeringPlanner,
)


NOW = datetime(2026, 7, 19, 21, 0, tzinfo=timezone.utc)
INTENT = (
    "Create a PostgreSQL migration and run a PostgreSQL service using "
    "PostgreSQL secret ref secret.postgres-test."
)


class NaturalPostgreSQLVerificationPlanBuilderTests(unittest.TestCase):
    def test_builds_candidate_only_reversible_plan_without_sql_effect(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self._write(root / "db/001.up.sql", "CREATE TABLE notes(id bigint);\n")
            self._write(root / "db/001.down.sql", "DROP TABLE notes;\n")
            definition, candidate, entries, environment = _inputs(root)

            plan = NaturalPostgreSQLVerificationPlanBuilder().build(
                definition,
                candidate,
                entries,
                ("db/001.up.sql", "db/001.down.sql"),
                environment,
                now=NOW,
            )

            self.assertEqual("fam_candidate", plan.database_name)
            self.assertEqual("fam_migrator", plan.migration_role)
            self.assertFalse(plan.production)
            self.assertEqual("secret.postgres-test", plan.connection_secret_ref)
            self.assertEqual(
                ("postgresql-migration-1-002827cbd6cf4a75",),
                tuple(item.asset_id for item in plan.migration_assets),
            )

    def test_rejects_psql_meta_commands_and_administrative_sql(self):
        for sql, diagnostic in (
            ("\\include /etc/passwd\n", "meta-commands"),
            ("CREATE ROLE escaped SUPERUSER;\n", "administrative"),
        ):
            with self.subTest(sql=sql), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                self._write(root / "db/001.up.sql", sql)
                self._write(root / "db/001.down.sql", "SELECT 1;\n")
                definition, candidate, entries, environment = _inputs(root)
                with self.assertRaisesRegex(PermissionError, diagnostic):
                    NaturalPostgreSQLVerificationPlanBuilder().build(
                        definition,
                        candidate,
                        entries,
                        ("db/001.up.sql", "db/001.down.sql"),
                        environment,
                        now=NOW,
                    )

    def test_requires_both_halves_of_changed_migration_pair(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self._write(root / "db/001.up.sql", "SELECT 1;\n")
            self._write(root / "db/001.down.sql", "SELECT 1;\n")
            definition, candidate, entries, environment = _inputs(root)
            with self.assertRaisesRegex(LookupError, "changed"):
                NaturalPostgreSQLVerificationPlanBuilder().build(
                    definition,
                    candidate,
                    entries,
                    ("db/001.up.sql",),
                    environment,
                    now=NOW,
                )

    @staticmethod
    def _write(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _inputs(root):
    owner = root.parent / f"owner-{root.name}"
    owner.mkdir()
    proposal = NaturalLanguageEngineeringPlanner().propose(
        prompt=INTENT,
        workspace_root=str(owner),
        owner_id="owner-1",
        principal_id="owner-1",
        task_id="task-postgresql-plan",
        grant_id="grant-postgresql-plan",
        toolchains=("sql",),
        now=NOW,
    )
    entries = tuple(
        CandidateBaselineEntry(
            path.relative_to(root).as_posix(),
            CandidateEntryKind.FILE,
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_size,
            False,
        )
        for path in sorted(root.rglob("*.sql"))
    )
    candidate = CandidateWorkspace(
        "candidate-postgresql-plan",
        "task-postgresql-plan",
        "baseline-1",
        str(owner),
        str(root),
        NOW,
        "copy",
        "a" * 64,
        entries,
    )
    environment = NaturalIntegrationEnvironmentPlanner("host-1").build(
        proposal.definition,
        candidate,
        tuple(item.path for item in entries),
        "changeset-postgresql-plan",
        (),
        postapply=False,
        now=NOW,
        resource_grant=proposal.integration_resource_grant,
    )
    return proposal.definition, candidate, entries, environment


if __name__ == "__main__":
    unittest.main()
