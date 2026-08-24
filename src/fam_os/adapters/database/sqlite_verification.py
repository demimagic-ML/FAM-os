"""Independent restore and declared-rollback rehearsal for SQLite plans."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

from fam_os.adapters.database.sqlite_digest import (
    sqlite_data_digest,
    sqlite_schema_digest,
)
from fam_os.adapters.database.sqlite_storage import open_snapshot
from fam_os.adapters.database.sqlite_policy import (
    clear_migration_authorizer,
    install_migration_authorizer,
)
from fam_os.core.engineering.database import DatabaseChangePlan


def verify_snapshot_restore(
    plaintext: bytes,
    directory: Path,
    plan: DatabaseChangePlan,
    identifier: Callable[[], str],
) -> str:
    restored, path = open_snapshot(plaintext, directory)
    try:
        if restored.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("database backup restore test failed")
        if (
            sqlite_schema_digest(restored) != plan.baseline_schema_sha256
            or sqlite_data_digest(restored) != plan.baseline_data_sha256
        ):
            raise RuntimeError("database backup content does not match baseline")
        return identifier()
    finally:
        restored.close()
        path.unlink(missing_ok=True)


def verify_declared_rollback(
    source: sqlite3.Connection,
    plan: DatabaseChangePlan,
    content_loader: Callable[[str, str], bytes],
    statement_parser: Callable[[str], tuple[str, ...]],
    live_check: Callable[[], None],
    identifier: Callable[[], str],
) -> str:
    rehearsal = sqlite3.connect(":memory:", isolation_level=None)
    source.backup(rehearsal)
    rehearsal.execute("PRAGMA foreign_keys=ON")
    install_migration_authorizer(rehearsal)
    rehearsal.execute("BEGIN IMMEDIATE")
    try:
        for step in reversed(plan.migration_steps):
            live_check()
            content = content_loader(step.rollback_path, step.rollback_sha256)
            for statement in statement_parser(content.decode("utf-8", "strict")):
                live_check()
                rehearsal.execute(statement)
        clear_migration_authorizer(rehearsal)
        if (
            sqlite_schema_digest(rehearsal) != plan.baseline_schema_sha256
            or sqlite_data_digest(rehearsal) != plan.baseline_data_sha256
        ):
            raise RuntimeError("declared database rollback does not restore baseline")
        rehearsal.rollback()
        return identifier()
    except BaseException:
        rehearsal.rollback()
        raise
    finally:
        clear_migration_authorizer(rehearsal)
        rehearsal.close()
