"""Encrypted owner-scoped opaque engineering secret references."""

from datetime import datetime
import re
from uuid import uuid4

from fam_os.product.storage.cipher import CipherContext


_REFERENCE = re.compile(r"secret\.[A-Za-z0-9_.-]{1,120}\Z")
_TOOL_KEY = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


class SqliteEngineeringSecretRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def provision(self, secret_ref, tool_key, consumer_id, value, at: datetime):
        self._validate(secret_ref, tool_key, consumer_id, value, at)
        row = self._row(secret_ref)
        if row is not None and row[3] == "active":
            raise FileExistsError("engineering secret reference is already active")
        generation = 1 if row is None else int(row[4]) + 1
        token = self._encrypt(secret_ref, generation, value)
        instant = at.isoformat()
        with self._database.transaction() as connection:
            connection.execute(
                "INSERT INTO engineering_secrets VALUES (?,?,?,?,?,?,?, ?,?) "
                "ON CONFLICT(secret_ref) DO UPDATE SET owner_id=excluded.owner_id,"
                "tool_key=excluded.tool_key,consumer_id=excluded.consumer_id,"
                "state='active',generation=excluded.generation,"
                "value_ciphertext=excluded.value_ciphertext,updated_at=excluded.updated_at",
                (secret_ref, self._owner_id, tool_key, consumer_id, "active",
                 generation, token, instant, instant),
            )
            self._audit(connection, secret_ref, "provisioned", generation, instant)
        return self.metadata(secret_ref)

    def rotate(self, secret_ref, value, at: datetime):
        row = self._active(secret_ref)
        self._validate(secret_ref, row[1], row[2], value, at)
        generation = int(row[4]) + 1
        token = self._encrypt(secret_ref, generation, value)
        instant = at.isoformat()
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE engineering_secrets SET generation=?,value_ciphertext=?,"
                "updated_at=? WHERE secret_ref=? AND state='active' AND generation=?",
                (generation, token, instant, secret_ref, row[4]),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("engineering secret changed concurrently")
            self._audit(connection, secret_ref, "rotated", generation, instant)
        return self.metadata(secret_ref)

    def delete(self, secret_ref, at: datetime):
        row = self._active(secret_ref)
        _aware(at)
        instant = at.isoformat()
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE engineering_secrets SET state='deleted',value_ciphertext=NULL,"
                "updated_at=? WHERE secret_ref=? AND state='active' AND generation=?",
                (instant, secret_ref, row[4]),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("engineering secret changed concurrently")
            self._audit(connection, secret_ref, "deleted", int(row[4]), instant)
        return self.metadata(secret_ref)

    def environment(self, secret_refs, consumer_id):
        values = {}
        for secret_ref in secret_refs:
            row = self._active(secret_ref)
            if row[2] != consumer_id:
                raise PermissionError("engineering secret consumer is mismatched")
            if row[1] in values:
                raise PermissionError("engineering secret tool keys collide")
            values[row[1]] = self._decrypt(secret_ref, int(row[4]), row[5])
        return values

    def metadata(self, secret_ref):
        row = self._row(secret_ref)
        if row is None:
            raise KeyError("engineering secret reference is unavailable")
        return {
            "secret_ref": row[0], "tool_key": row[1], "consumer_id": row[2],
            "state": row[3], "generation": row[4],
            "created_at": row[6], "updated_at": row[7],
        }

    def list_metadata(self):
        rows = self._database.fetchall(
            "SELECT secret_ref FROM engineering_secrets WHERE owner_id=? ORDER BY secret_ref",
            (self._owner_id,),
        )
        return tuple(self.metadata(row[0]) for row in rows)

    def audit(self, secret_ref):
        return tuple({
            "event_id": row[0], "action": row[1], "generation": row[2],
            "occurred_at": row[3],
        } for row in self._database.fetchall(
            "SELECT event_id,action,generation,occurred_at FROM engineering_secret_audit "
            "WHERE secret_ref=? ORDER BY sequence", (secret_ref,),
        ))

    def _row(self, secret_ref):
        if not isinstance(secret_ref, str) or not _REFERENCE.fullmatch(secret_ref):
            raise ValueError("engineering secret reference is invalid")
        return self._database.fetchone(
            "SELECT secret_ref,tool_key,consumer_id,state,generation,value_ciphertext,"
            "created_at,updated_at FROM engineering_secrets WHERE secret_ref=? AND owner_id=?",
            (secret_ref, self._owner_id),
        )

    def _active(self, secret_ref):
        row = self._row(secret_ref)
        if row is None or row[3] != "active" or not isinstance(row[5], str):
            raise KeyError("engineering secret reference is not active")
        return row

    def _encrypt(self, secret_ref, generation, value):
        return self._cipher.encrypt(self._context(secret_ref, generation), value.encode())

    def _decrypt(self, secret_ref, generation, token):
        return self._cipher.decrypt(self._context(secret_ref, generation), token).decode("utf-8", "strict")

    def _context(self, secret_ref, generation):
        return CipherContext(
            self._owner_id, "engineering-secret", secret_ref, f"value-v{generation}",
        )

    @staticmethod
    def _audit(connection, secret_ref, action, generation, instant):
        connection.execute(
            "INSERT INTO engineering_secret_audit VALUES (NULL,?,?,?,?,?)",
            (f"secret-event-{uuid4().hex}", secret_ref, action, generation, instant),
        )

    @staticmethod
    def _validate(secret_ref, tool_key, consumer_id, value, at):
        if not isinstance(secret_ref, str) or not _REFERENCE.fullmatch(secret_ref):
            raise ValueError("engineering secret reference is invalid")
        if not isinstance(tool_key, str) or not _TOOL_KEY.fullmatch(tool_key):
            raise ValueError("engineering secret tool key is invalid")
        if not isinstance(consumer_id, str) or not consumer_id.strip() or len(consumer_id) > 200:
            raise ValueError("engineering secret consumer is invalid")
        if not isinstance(value, str) or not value or "\0" in value or len(value.encode()) > 65_536:
            raise ValueError("engineering secret value is invalid")
        _aware(at)


def _aware(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("engineering secret instant must be timezone aware")
