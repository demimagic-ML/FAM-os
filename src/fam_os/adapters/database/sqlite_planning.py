"""Deterministic natural planning for candidate SQLite migrations."""

from __future__ import annotations

import hashlib
import re
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from fam_os.adapters.database.sqlite_digest import (
    sqlite_data_digest, sqlite_schema_digest,
)
from fam_os.adapters.database.sqlite_fixtures import (
    inspect_fixture_manifest, load_fixtures,
)
from fam_os.adapters.database.sqlite_policy import (
    clear_migration_authorizer, install_migration_authorizer,
)
from fam_os.adapters.database.sqlite_sql import split_migration_statements
from fam_os.adapters.database.sqlite_storage import secure_database_path
from fam_os.adapters.filesystem.candidate_io import contained, read_regular
from fam_os.core.engineering import (
    DatabaseChangePlan, DatabaseEngine, DatabaseEnvironment,
    DatabaseFixtureSet, DatabaseMigrationStep, DatabaseTarget,
    EngineeringAuthority, EngineeringResourceImpact,
)


_DATABASE_INTENT = re.compile(
    r"\b(?:database|sqlite|schema migration|migration|migrate|fixtures?)\b",
)
_REMOTE_DATABASE_INTENT = re.compile(r"\b(?:postgres(?:ql)?|mysql)\b")
_DESTRUCTIVE_SQL = re.compile(
    r"\b(?:ALTER|DELETE|DROP|REINDEX|REPLACE|UPDATE|VACUUM)\b", re.I,
)
_DATABASE_SUFFIXES = (".db", ".sqlite", ".sqlite3")


class NaturalSQLitePlanBuilder:
    """Derive exact plans from trusted task state and untrusted candidate assets."""

    def __init__(self, exact_host_id: str) -> None:
        if not exact_host_id.strip():
            raise ValueError("database planning requires an exact host identity")
        self._exact_host_id = exact_host_id

    @staticmethod
    def requested(intent: str) -> bool:
        normalized = " ".join(intent.casefold().split())
        return (
            _REMOTE_DATABASE_INTENT.search(normalized) is None
            and _DATABASE_INTENT.search(normalized) is not None
        )

    def build(
        self, definition, candidate, entries, changed_paths, changeset_id: str,
        *, now: datetime,
    ) -> DatabaseChangePlan | None:
        if not self.requested(definition.task.intent):
            return None
        files = {item.path: item for item in entries if item.kind.value == "file"}
        database_path = _database_target(definition.task.intent, files)
        pairs = _migration_pairs(files, tuple(changed_paths))
        if not pairs:
            raise LookupError("database intent requires a changed forward/rollback SQL pair")
        root = Path(candidate.candidate_workspace)
        database = secure_database_path(root, database_path)
        content = {
            path: _content(root, path) for pair in pairs for path in pair
        }
        fixture = _fixture(root, files, tuple(changed_paths))
        baseline_schema, baseline_data, expected = _preflight(
            database, pairs, content, fixture, root,
        )
        steps = tuple(
            DatabaseMigrationStep(
                f"migration-{index}-{_short(forward)}", index,
                forward, _sha(content[forward]), rollback,
                _sha(content[rollback]),
                _DESTRUCTIVE_SQL.search(
                    content[forward].decode("utf-8", "strict")
                ) is not None,
                True, expected[index - 1],
            )
            for index, (forward, rollback) in enumerate(pairs, 1)
        )
        identity = _sha(
            "|".join((
                definition.task.task_id, candidate.candidate_id, database_path,
                changeset_id, *(item.forward_sha256 for item in steps),
                *(item.rollback_sha256 for item in steps),
            )).encode("utf-8")
        )[:32]
        target = DatabaseTarget(
            f"database-target-{identity}", DatabaseEngine.SQLITE,
            DatabaseEnvironment.CANDIDATE, database_path, None,
            self._exact_host_id, False,
        )
        task = definition.task
        return DatabaseChangePlan(
            f"database-plan-{identity}", task.task_id, candidate.candidate_id,
            target, baseline_schema, baseline_data, steps, fixture, True, True,
            ("schema-match", "foreign-keys", "transaction-test"),
            (EngineeringAuthority.EXECUTE, EngineeringAuthority.MODIFY),
            EngineeringResourceImpact(
                min(task.max_wall_seconds, 300), 1, 0,
                min(
                    task.max_changed_files,
                    1 + len(content) + int(fixture is not None),
                ),
                task.max_changed_bytes, 0,
            ),
            changeset_id, now,
        )


def _database_target(intent: str, files: dict) -> str:
    candidates = tuple(sorted(
        path for path in files if path.casefold().endswith(_DATABASE_SUFFIXES)
    ))
    mentioned = tuple(
        path for path in candidates if path.casefold() in intent.casefold()
    )
    selected = mentioned or candidates
    if len(selected) != 1:
        raise LookupError(
            "database intent must identify exactly one candidate SQLite file"
        )
    return selected[0]


def _migration_pairs(files: dict, changed_paths: tuple[str, ...]):
    pairs = []
    for path in sorted(set(changed_paths)):
        rollback = _rollback_path(path)
        if rollback is not None and path in files and rollback in files:
            pairs.append((path, rollback))
    return tuple(pairs)


def _rollback_path(path: str) -> str | None:
    if path.endswith(".up.sql"):
        return path[:-7] + ".down.sql"
    if path.endswith("_up.sql"):
        return path[:-7] + "_down.sql"
    if path.endswith(".sql") and not path.endswith(("_down.sql", ".down.sql")):
        return path[:-4] + "_down.sql"
    return None


def _fixture(root: Path, files: dict, changed_paths: tuple[str, ...]):
    paths = tuple(sorted(
        path for path in changed_paths
        if path in files and PurePosixPath(path).name == "fixtures.json"
    ))
    if len(paths) > 1:
        raise LookupError("database intent has multiple changed fixture manifests")
    if not paths:
        return None
    raw = _content(root, paths[0])
    _document, count = inspect_fixture_manifest(raw)
    return DatabaseFixtureSet(
        f"fixture-{_short(paths[0])}", paths[0], _sha(raw), count, True, False,
    )


def _preflight(database, pairs, content, fixture, root):
    source = sqlite3.connect(database)
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "preflight.sqlite3"
        trial = sqlite3.connect(path, isolation_level=None)
        try:
            source.backup(trial)
            baseline_schema = sqlite_schema_digest(trial)
            baseline_data = sqlite_data_digest(trial)
            install_migration_authorizer(trial)
            trial.execute("BEGIN IMMEDIATE")
            expected = []
            for forward, _rollback in pairs:
                _execute(trial, content[forward])
                expected.append(sqlite_schema_digest(trial))
            if fixture is not None:
                load_fixtures(
                    trial, fixture,
                    lambda path, digest: _checked_content(root, path, digest),
                    lambda: None,
                )
            for _forward, rollback in reversed(pairs):
                _execute(trial, content[rollback])
            clear_migration_authorizer(trial)
            if (
                sqlite_schema_digest(trial) != baseline_schema
                or sqlite_data_digest(trial) != baseline_data
            ):
                raise RuntimeError(
                    "declared database rollback does not restore baseline"
                )
            trial.rollback()
            return baseline_schema, baseline_data, tuple(expected)
        finally:
            clear_migration_authorizer(trial)
            trial.close()
            source.close()


def _execute(connection, raw: bytes) -> None:
    for statement in split_migration_statements(raw.decode("utf-8", "strict")):
        connection.execute(statement)


def _content(root: Path, relative: str) -> bytes:
    return read_regular(contained(root, relative), 4 * 1024 * 1024)


def _checked_content(root: Path, relative: str, expected: str) -> bytes:
    raw = _content(root, relative)
    if _sha(raw) != expected:
        raise RuntimeError(
            "database candidate content digest changed during planning"
        )
    return raw


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _short(value: str) -> str:
    return _sha(value.encode("utf-8"))[:16]
