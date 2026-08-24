import hashlib
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.database import NaturalSQLitePlanBuilder
from fam_os.core.engineering import (
    CandidateBaselineEntry, CandidateEntryKind, CandidateWorkspace,
    NaturalLanguageEngineeringPlanner,
)


NOW = datetime(2026, 7, 19, 20, 0, tzinfo=timezone.utc)


class NaturalSQLitePlanBuilderTests(unittest.TestCase):
    def test_builds_exact_plan_without_mutating_candidate_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self._database(root / "app.db")
            self._write(root / "db/001.sql", "CREATE TABLE notes(id INTEGER);")
            self._write(root / "db/001_down.sql", "DROP TABLE notes;")
            definition, candidate, entries = _inputs(root)

            plan = NaturalSQLitePlanBuilder("host-1").build(
                definition, candidate, entries,
                ("db/001.sql", "db/001_down.sql"), "changeset-1", now=NOW,
            )

            self.assertEqual("app.db", plan.target.database_name)
            self.assertEqual(("migration-1-851b0d7d9b2e9c10",), tuple(
                item.step_id for item in plan.migration_steps
            ))
            self.assertEqual(["users"], _tables(root / "app.db"))

    def test_requires_one_database_and_one_changed_rollback_pair(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self._database(root / "app.db")
            self._database(root / "other.db")
            self._write(root / "db/001.sql", "CREATE TABLE notes(id INTEGER);")
            definition, candidate, entries = _inputs(
                root, intent="Create a SQLite database migration.",
            )
            with self.assertRaisesRegex(LookupError, "exactly one"):
                NaturalSQLitePlanBuilder("host-1").build(
                    definition, candidate, entries, ("db/001.sql",),
                    "changeset-1", now=NOW,
                )

    def test_preflight_denies_host_database_attachment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            outside = root.parent / f"outside-{root.name}.db"
            self._database(root / "app.db")
            self._write(
                root / "db/001.sql",
                f"ATTACH DATABASE '{outside}' AS escaped;",
            )
            self._write(root / "db/001_down.sql", "SELECT 1;")
            definition, candidate, entries = _inputs(root)
            with self.assertRaises(sqlite3.DatabaseError):
                NaturalSQLitePlanBuilder("host-1").build(
                    definition, candidate, entries,
                    ("db/001.sql", "db/001_down.sql"),
                    "changeset-1", now=NOW,
                )
            self.assertFalse(outside.exists())

    @staticmethod
    def _database(path):
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE users(id INTEGER PRIMARY KEY) STRICT")
        connection.commit()
        connection.close()

    @staticmethod
    def _write(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def _inputs(root, intent="Create a SQLite migration for app.db adding notes."):
    proposal = NaturalLanguageEngineeringPlanner().propose(
        prompt=intent, workspace_root=str(root.parent / "owner"),
        owner_id="owner-1", principal_id="owner-1", task_id="task-1",
        grant_id="grant-1", toolchains=(), now=NOW,
    )
    entries = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            entries.append(CandidateBaselineEntry(
                relative, CandidateEntryKind.DIRECTORY, None, 0, False,
            ))
        else:
            raw = path.read_bytes()
            entries.append(CandidateBaselineEntry(
                relative, CandidateEntryKind.FILE,
                hashlib.sha256(raw).hexdigest(), len(raw), False,
            ))
    candidate = CandidateWorkspace(
        "candidate-1", "task-1", "baseline-1", str(root.parent / "owner"),
        str(root), NOW, "copy", "a" * 64, (),
    )
    return proposal.definition, candidate, tuple(entries)


def _tables(database):
    connection = sqlite3.connect(database)
    try:
        return [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"
        )]
    finally:
        connection.close()


if __name__ == "__main__":
    unittest.main()
