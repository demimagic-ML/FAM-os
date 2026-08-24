"""Fixed no-shell commands for one isolated PostgreSQL container."""

from __future__ import annotations

import hashlib


_ROLE_SQL = (
    'CREATE ROLE "fam_migrator" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
    'NOINHERIT NOREPLICATION NOBYPASSRLS;'
)
_DATABASE_SQL = (
    'CREATE DATABASE "fam_candidate" OWNER "fam_migrator" TEMPLATE template0;'
)
_RESTORE_DATABASE_SQL = (
    'CREATE DATABASE "fam_restore" OWNER "fam_migrator" TEMPLATE template0;'
)
_DROP_CANDIDATE_SQL = 'DROP DATABASE "fam_candidate" WITH (FORCE);'
_ROLE_EVIDENCE_SQL = (
    "SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,rolinherit,"
    "rolreplication,rolbypassrls FROM pg_roles WHERE rolname='fam_migrator';"
)


class PostgreSQLContainerCommands:
    """Execute only release-owned command shapes against an admitted runtime."""

    def __init__(self, client, runtime_id: str, control) -> None:
        self._client = client
        self._runtime_id = runtime_id
        self._control = control

    def setup(self) -> None:
        self._psql("postgres", "postgres", ("--command", _ROLE_SQL), "role creation")
        self._psql(
            "postgres", "postgres", ("--command", _DATABASE_SQL),
            "candidate database creation",
        )
        evidence = self._psql(
            "postgres",
            "postgres",
            ("--tuples-only", "--no-align", "--command", _ROLE_EVIDENCE_SQL),
            "restricted role inspection",
        ).decode("utf-8", "strict").strip()
        if evidence != "fam_migrator|f|f|f|f|f|f":
            raise PermissionError("PostgreSQL migration role is not restricted")

    def apply(self, sql: bytes, database: str = "fam_candidate") -> None:
        self._psql_input(
            "fam_migrator",
            database,
            ("--single-transaction",),
            "candidate PostgreSQL migration",
            sql,
            timeout=120,
        )

    def transaction_probe(self, identity: str) -> None:
        table = f'"__fam_transaction_{identity[:16]}"'
        sql = f"BEGIN; CREATE TABLE {table}(value bigint); ROLLBACK;"
        self._psql(
            "fam_migrator", "fam_candidate", ("--command", sql),
            "PostgreSQL transaction probe",
        )

    def digest(self, database: str) -> tuple[str, str]:
        schema = self._dump(database, "--schema-only")
        data = self._dump(
            database,
            "--data-only",
            "--column-inserts",
            "--rows-per-insert=1",
        )
        return _digest_dump(schema), _digest_dump(data)

    def backup(self) -> bytes:
        return self._dump("fam_candidate", "--format=custom")

    def restore(self, backup: bytes) -> None:
        self._psql(
            "postgres",
            "postgres",
            ("--command", _RESTORE_DATABASE_SQL),
            "PostgreSQL restore database creation",
        )
        self._restore_into(backup, "fam_restore")

    def recover_candidate(self, backup: bytes) -> None:
        """Return a failed disposable verification database to its baseline."""

        self._psql(
            "postgres", "postgres", ("--command", _DROP_CANDIDATE_SQL),
            "PostgreSQL failed candidate removal",
        )
        self._psql(
            "postgres", "postgres", ("--command", _DATABASE_SQL),
            "PostgreSQL failed candidate recreation",
        )
        self._restore_into(backup, "fam_candidate")

    def _restore_into(self, backup: bytes, database: str) -> None:
        self._exec_input(
            "postgres",
            (
                "pg_restore", "--exit-on-error", "--single-transaction",
                "--no-owner", "--no-privileges", "--username=fam_migrator",
                f"--dbname={database}",
            ),
            "PostgreSQL backup restore",
            backup,
            timeout=120,
        )

    def cleanup(self) -> None:
        return None

    def _dump(self, database: str, *options: str) -> bytes:
        return self._exec(
            "postgres",
            (
                "pg_dump", "--no-owner", "--no-privileges", "--no-comments",
                "--encoding=UTF8", f"--dbname={database}", *options,
            ),
            "PostgreSQL bounded dump",
            timeout=120,
        )

    def _psql(self, username, database, options, action, timeout=30) -> bytes:
        return self._exec(
            "postgres",
            (
                "psql", "--no-psqlrc", "--set=ON_ERROR_STOP=1",
                f"--username={username}", f"--dbname={database}", *options,
            ),
            action,
            timeout=timeout,
        )

    def _psql_input(
        self, username, database, options, action, content, timeout=30,
    ) -> bytes:
        return self._exec_input(
            "postgres",
            (
                "psql", "--no-psqlrc", "--set=ON_ERROR_STOP=1",
                f"--username={username}", f"--dbname={database}", *options,
            ),
            action,
            content,
            timeout=timeout,
        )

    def _exec(self, user, command, action, timeout=30) -> bytes:
        self._live()
        result = self._client.run(
            ("exec", "--user", user, self._runtime_id, *command),
            timeout_seconds=timeout,
        )
        output = self._required(result, action)
        self._live()
        return output

    def _exec_input(self, user, command, action, content, timeout=30) -> bytes:
        self._live()
        result = self._client.run_with_input(
            ("exec", "--interactive", "--user", user, self._runtime_id, *command),
            content,
            timeout_seconds=timeout,
        )
        output = self._required(result, action)
        self._live()
        return output

    @staticmethod
    def _required(result, action) -> bytes:
        if result.exit_code != 0:
            raise RuntimeError(f"{action} failed")
        return result.output

    def _live(self) -> None:
        if self._control.cancelled() or not self._control.authorization_active():
            raise PermissionError("PostgreSQL verification was cancelled or revoked")


def _digest_dump(raw: bytes) -> str:
    """Remove pg_dump's random psql restriction key, not database content."""

    lines = []
    for line in raw.replace(b"\r\n", b"\n").splitlines():
        stripped = line.lstrip()
        if stripped.startswith((b"\\restrict ", b"\\unrestrict ", b"--")):
            continue
        lines.append(line.rstrip())
    normalized = b"\n".join(lines).strip() + b"\n"
    return hashlib.sha256(normalized).hexdigest()
