"""Private SQLite WAL database and ordered migration lifecycle."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from threading import RLock
from typing import Iterator


@dataclass(frozen=True, slots=True)
class StorageSettings:
    path: Path
    owner_uid: int
    busy_timeout_ms: int = 5_000

    def __post_init__(self) -> None:
        if self.owner_uid < 0 or self.busy_timeout_ms < 1:
            raise ValueError("storage settings are invalid")


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str

    def __post_init__(self) -> None:
        if self.version < 1 or not self.name.replace("_", "").isalnum():
            raise ValueError("migration identity is invalid")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


class ProductionDatabase:
    def __init__(self, settings: StorageSettings) -> None:
        self.settings = settings
        self._connection: sqlite3.Connection | None = None
        self._lock = RLock()

    def open(self) -> None:
        if self._connection is not None:
            return
        _prepare_private_path(self.settings)
        connection = sqlite3.connect(
            self.settings.path,
            timeout=self.settings.busy_timeout_ms / 1_000,
            isolation_level=None,
            check_same_thread=False,
        )
        try:
            _configure(connection, self.settings.busy_timeout_ms)
            apply_migrations(connection, bundled_migrations())
            _verify_database(connection)
        except BaseException:
            connection.close()
            raise
        self._connection = connection

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def execute(
        self,
        statement: str,
        parameters: tuple[object, ...] = (),
    ) -> sqlite3.Cursor:
        with self._lock:
            return self.connection.execute(statement, parameters)

    def fetchone(
        self,
        statement: str,
        parameters: tuple[object, ...] = (),
    ) -> tuple[object, ...] | None:
        """Execute and fetch one row while retaining the connection lock."""
        with self._lock:
            return self.connection.execute(statement, parameters).fetchone()

    def fetchall(
        self,
        statement: str,
        parameters: tuple[object, ...] = (),
    ) -> list[tuple[object, ...]]:
        """Execute and fetch every row while retaining the connection lock."""
        with self._lock:
            return self.connection.execute(statement, parameters).fetchall()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = self.connection
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("production database is not open")
        return self._connection


def bundled_migrations() -> tuple[Migration, ...]:
    root = files("fam_os.product.storage.migrations")
    migrations = []
    for item in sorted(root.iterdir(), key=lambda candidate: candidate.name):
        if item.name.endswith(".sql"):
            version_text, name = item.name[:-4].split("_", 1)
            migrations.append(Migration(int(version_text), name, item.read_text("utf-8")))
    versions = tuple(item.version for item in migrations)
    if versions != tuple(range(1, len(migrations) + 1)):
        raise RuntimeError("storage migrations must be contiguous from version 1")
    return tuple(migrations)


def apply_migrations(
    connection: sqlite3.Connection,
    migrations: tuple[Migration, ...],
) -> None:
    _ensure_migration_table(connection)
    applied = {
        row[0]: row[1]
        for row in connection.execute("SELECT version, sha256 FROM schema_migrations")
    }
    known_versions = {item.version for item in migrations}
    if set(applied) - known_versions:
        raise RuntimeError("database contains an unknown future migration")
    for migration in migrations:
        digest = applied.get(migration.version)
        if digest is not None:
            if digest != migration.sha256:
                raise RuntimeError(f"migration {migration.version} digest changed")
            continue
        _apply_migration(connection, migration)


def _apply_migration(connection: sqlite3.Connection, migration: Migration) -> None:
    name = migration.name.replace("'", "''")
    applied = "strftime('%Y-%m-%dT%H:%M:%fZ','now')"
    record = (
        "INSERT INTO schema_migrations(version,name,sha256,applied_at) VALUES "
        f"({migration.version},'{name}','{migration.sha256}',{applied});"
    )
    try:
        connection.executescript(f"BEGIN IMMEDIATE;\n{migration.sql}\n{record}\nCOMMIT;")
    except BaseException:
        connection.rollback()
        raise


def _ensure_migration_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations("
        "version INTEGER PRIMARY KEY,name TEXT NOT NULL,sha256 TEXT NOT NULL,"
        "applied_at TEXT NOT NULL) STRICT"
    )


def _prepare_private_path(settings: StorageSettings) -> None:
    parent = settings.path.parent
    if parent.is_symlink() or settings.path.is_symlink():
        raise OSError("database path cannot contain a final symlink")
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(parent, 0o700)
    _verify_owner_mode(parent, settings.owner_uid, 0o700, directory=True)
    if not settings.path.exists():
        descriptor = os.open(settings.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
    os.chmod(settings.path, 0o600)
    _verify_owner_mode(settings.path, settings.owner_uid, 0o600, directory=False)


def _verify_owner_mode(path: Path, uid: int, mode: int, *, directory: bool) -> None:
    metadata = path.stat(follow_symlinks=False)
    if metadata.st_uid != uid or stat.S_IMODE(metadata.st_mode) != mode:
        raise PermissionError(f"{path.name} has unsafe owner or mode")
    if directory != stat.S_ISDIR(metadata.st_mode):
        raise OSError(f"{path.name} has the wrong file type")
    if not directory and metadata.st_nlink != 1:
        raise OSError("database file must have exactly one hard link")


def _configure(connection: sqlite3.Connection, timeout_ms: int) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {timeout_ms:d}")
    connection.execute("PRAGMA synchronous = FULL")
    mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
    if mode.lower() != "wal":
        raise RuntimeError("SQLite WAL mode is unavailable")


def _verify_database(connection: sqlite3.Connection) -> None:
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("SQLite integrity check failed")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise RuntimeError("SQLite foreign keys are disabled")
