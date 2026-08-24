"""Strict SQLite migration script splitting shared by planning and execution."""

import re
import sqlite3


_TRANSACTION = re.compile(
    r"\b(?:BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE)\b", re.I,
)


def split_migration_statements(script: str) -> tuple[str, ...]:
    """Return complete statements while reserving transaction control to FAM."""
    if _TRANSACTION.search(script):
        raise ValueError("migration SQL cannot control the adapter transaction")
    pending = ""
    statements = []
    for character in script:
        pending += character
        if character == ";" and sqlite3.complete_statement(pending):
            statements.append(pending.strip())
            pending = ""
    if pending.strip():
        raise ValueError("migration SQL contains an incomplete statement")
    if not statements:
        raise ValueError("migration SQL contains no statements")
    return tuple(statements)
