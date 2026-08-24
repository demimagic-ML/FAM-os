"""Canonical, content-sensitive SQLite schema and data fingerprints."""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from typing import Any


def _hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def sqlite_schema_digest(connection: sqlite3.Connection) -> str:
    rows = connection.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_schema "
        "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
        "ORDER BY type,name,tbl_name,sql"
    ).fetchall()
    return _hash([[str(value) for value in row] for row in rows])


def sqlite_data_digest(connection: sqlite3.Connection) -> str:
    tables = [
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    payload = []
    for table in tables:
        quoted = _identifier(table)
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({quoted})")]
        order = ",".join(_identifier(column) for column in columns)
        query = f"SELECT * FROM {quoted}" + (f" ORDER BY {order}" if order else "")
        rows = [[_typed(value) for value in row] for row in connection.execute(query)]
        payload.append({"table": table, "columns": columns, "rows": rows})
    return _hash(payload)


def _identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _typed(value: Any) -> object:
    if value is None:
        return ["null", None]
    if isinstance(value, bytes):
        return ["blob", base64.b64encode(value).decode("ascii")]
    if isinstance(value, bool):
        return ["integer", int(value)]
    if isinstance(value, int):
        return ["integer", value]
    if isinstance(value, float):
        return ["real", value.hex()]
    return ["text", str(value)]
