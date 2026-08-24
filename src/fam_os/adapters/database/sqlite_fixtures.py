"""Strict parameterized loading of synthetic SQLite fixture manifests."""

import json
import re
import sqlite3
from collections.abc import Callable

from fam_os.core.engineering.database import DatabaseFixtureSet


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def load_fixtures(
    connection: sqlite3.Connection,
    fixture: DatabaseFixtureSet,
    content_loader: Callable[[str, str], bytes],
    live_check: Callable[[], None],
) -> None:
    raw = content_loader(fixture.manifest_path, fixture.manifest_sha256)
    document, declared_count = inspect_fixture_manifest(raw)
    if declared_count != fixture.row_count:
        raise ValueError("database fixture row count does not match its contract")
    count = 0
    for table in document["tables"]:
        name, columns, rows = table["name"], table["columns"], table["rows"]
        placeholders = ",".join("?" for _ in columns)
        sql = f"INSERT INTO {_quote(name)} ({','.join(map(_quote, columns))}) VALUES ({placeholders})"
        for row in rows:
            live_check()
            connection.execute(sql, tuple(row))
            count += 1
    if count != fixture.row_count:
        raise ValueError("database fixture row count does not match its contract")


def inspect_fixture_manifest(raw: bytes) -> tuple[dict, int]:
    """Validate one secret-free parameterized fixture document and count rows."""
    document = json.loads(raw.decode("utf-8", "strict"))
    if set(document) != {"tables"} or not isinstance(document["tables"], list):
        raise ValueError("database fixture manifest has an invalid shape")
    count = 0
    for table in document["tables"]:
        if set(table) != {"name", "columns", "rows"}:
            raise ValueError("database fixture table has an invalid shape")
        name, columns, rows = table["name"], table["columns"], table["rows"]
        if not _IDENTIFIER.fullmatch(name) or not columns:
            raise ValueError("database fixture identifier is invalid")
        if any(
            not isinstance(item, str) or not _IDENTIFIER.fullmatch(item)
            for item in columns
        ):
            raise ValueError("database fixture column is invalid")
        for row in rows:
            if not isinstance(row, list) or len(row) != len(columns):
                raise ValueError("database fixture row width is invalid")
            count += 1
    return document, count


def _quote(identifier: str) -> str:
    return f'"{identifier}"'
