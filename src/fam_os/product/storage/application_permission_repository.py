"""Encrypted durable permission grants for Application Fabric actions."""

from dataclasses import replace
from datetime import datetime

from fam_os.applications import PermissionGrant
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqliteApplicationPermissionRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def put(self, grant: PermissionGrant) -> None:
        token = self._encode(grant)
        state = "revoked" if grant.revoked_at is not None else "active"
        with self._database.transaction() as connection:
            connection.execute(
                "INSERT INTO application_permissions(grant_id,subject_id,state,"
                "payload_ciphertext) VALUES (?,?,?,?) ON CONFLICT(grant_id) DO UPDATE "
                "SET subject_id=excluded.subject_id,state=excluded.state,"
                "payload_ciphertext=excluded.payload_ciphertext,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')",
                (grant.grant_id, grant.subject_id, state, token),
            )

    def get(self, grant_id: str) -> PermissionGrant | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM application_permissions WHERE grant_id=?",
            (grant_id,),
        )
        return None if row is None else self._decode(grant_id, row[0])

    def revoke(self, grant_id: str, revoked_at: datetime) -> bool:
        grant = self.get(grant_id)
        if grant is None or grant.revoked_at is not None:
            return False
        self.put(replace(grant, revoked_at=revoked_at))
        return True

    def active(self, subject_id: str, instant: datetime) -> tuple[PermissionGrant, ...]:
        rows = self._database.fetchall(
            "SELECT grant_id,payload_ciphertext FROM application_permissions "
            "WHERE subject_id=? AND state='active' ORDER BY grant_id",
            (subject_id,),
        )
        grants = tuple(self._decode(row[0], row[1]) for row in rows)
        return tuple(grant for grant in grants if grant.active_at(instant))

    def active_count(self, instant: datetime) -> int:
        """Count currently effective grants without exposing their payloads."""
        rows = self._database.fetchall(
            "SELECT grant_id,payload_ciphertext FROM application_permissions "
            "WHERE state='active' ORDER BY grant_id",
        )
        return sum(
            1 for grant_id, token in rows
            if self._decode(grant_id, token).active_at(instant)
        )

    def _encode(self, grant: PermissionGrant) -> str:
        return encrypt_contract(
            self._cipher, self._owner_id, "application-permission",
            grant.grant_id, grant,
        )

    def _decode(self, grant_id: object, token: object) -> PermissionGrant:
        if not isinstance(grant_id, str) or not isinstance(token, str):
            raise TypeError("stored application permission has invalid fields")
        value = decrypt_contract(
            self._cipher, self._owner_id, "application-permission",
            grant_id, token, PermissionGrant,
        )
        assert isinstance(value, PermissionGrant)
        return value
