"""SQLite authorizer that confines migration SQL to its opened database."""

import sqlite3


_DENIED_ACTIONS = frozenset(
    action for action in (
        getattr(sqlite3, "SQLITE_ATTACH", None),
        getattr(sqlite3, "SQLITE_DETACH", None),
        getattr(sqlite3, "SQLITE_PRAGMA", None),
        getattr(sqlite3, "SQLITE_CREATE_VTABLE", None),
        getattr(sqlite3, "SQLITE_DROP_VTABLE", None),
    ) if action is not None
)
_DENIED_FUNCTIONS = frozenset({"load_extension", "readfile", "writefile"})


def install_migration_authorizer(connection: sqlite3.Connection) -> None:
    def authorize(action, _first, second, _database, _trigger):
        if action in _DENIED_ACTIONS:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION and str(second).lower() in _DENIED_FUNCTIONS:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    connection.set_authorizer(authorize)


def clear_migration_authorizer(connection: sqlite3.Connection) -> None:
    connection.set_authorizer(None)
