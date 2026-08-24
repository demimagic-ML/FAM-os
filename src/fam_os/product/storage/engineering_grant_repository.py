"""Encrypted restart-safe storage for owner engineering grants and decisions."""

from __future__ import annotations

from fam_os.core.engineering.grants import (
    EngineeringAuthorityGrant,
    EngineeringAuthorizationDecision,
    GrantLifecycleState,
    OwnerGrantApproval,
)
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqliteEngineeringGrantRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def put(
        self, grant: EngineeringAuthorityGrant, approval: OwnerGrantApproval,
    ) -> None:
        if grant.owner_id != self._owner_id or approval.owner_id != self._owner_id:
            raise PermissionError("engineering grant owner does not match storage owner")
        grant_token = self._encode("engineering-grant", grant.grant_id, grant)
        approval_token = self._encode(
            "engineering-grant-approval", grant.grant_id, approval,
        )
        with self._database.transaction() as connection:
            connection.execute(
                "INSERT INTO engineering_grants VALUES (?,?,?,?,1,?,?,"
                "strftime('%Y-%m-%dT%H:%M:%fZ','now')) "
                "ON CONFLICT(grant_id) DO UPDATE SET owner_id=excluded.owner_id,"
                "principal_id=excluded.principal_id,state=excluded.state,"
                "reconfirmation_required=1,grant_ciphertext=excluded.grant_ciphertext,"
                "approval_ciphertext=excluded.approval_ciphertext,"
                "updated_at=excluded.updated_at",
                (
                    grant.grant_id, grant.owner_id, grant.principal_id,
                    grant.state.value, grant_token, approval_token,
                ),
            )

    def get(
        self, grant_id: str,
    ) -> tuple[EngineeringAuthorityGrant, OwnerGrantApproval, bool] | None:
        row = self._database.fetchone(
            "SELECT grant_ciphertext,approval_ciphertext,reconfirmation_required "
            "FROM engineering_grants WHERE grant_id=?", (grant_id,),
        )
        if row is None:
            return None
        grant = self._decode(
            "engineering-grant", grant_id, row[0], EngineeringAuthorityGrant,
        )
        approval = self._decode(
            "engineering-grant-approval", grant_id, row[1], OwnerGrantApproval,
        )
        return grant, approval, bool(row[2])

    def mark_reconfirmed(self, grant_id: str) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE engineering_grants SET reconfirmation_required=0,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE grant_id=? AND state='active'", (grant_id,),
            )
        return cursor.rowcount == 1

    def require_restart_reconfirmation(self) -> int:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE engineering_grants SET reconfirmation_required=1,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE state='active' AND reconfirmation_required=0"
            )
        return cursor.rowcount

    def usable(self, grant_id: str) -> EngineeringAuthorityGrant | None:
        stored = self.get(grant_id)
        if stored is None or stored[2]:
            return None
        grant = stored[0]
        return grant if grant.state is GrantLifecycleState.ACTIVE else None

    def record_decision(self, decision: EngineeringAuthorizationDecision) -> None:
        token = self._encode(
            "engineering-authorization", decision.decision_id, decision,
        )
        with self._database.transaction() as connection:
            connection.execute(
                "INSERT INTO engineering_authorization_audit"
                "(decision_id,grant_id,authority,allowed,decision_ciphertext) "
                "VALUES (?,?,?,?,?)",
                (
                    decision.decision_id, decision.grant_id,
                    decision.authority.value, int(decision.allowed), token,
                ),
            )

    def decisions(self, grant_id: str) -> tuple[EngineeringAuthorizationDecision, ...]:
        rows = self._database.fetchall(
            "SELECT decision_id,decision_ciphertext FROM engineering_authorization_audit "
            "WHERE grant_id=? ORDER BY sequence", (grant_id,),
        )
        return tuple(
            self._decode(
                "engineering-authorization", row[0], row[1],
                EngineeringAuthorizationDecision,
            )
            for row in rows
        )

    def _encode(self, kind, identity, value) -> str:
        return encrypt_contract(
            self._cipher, self._owner_id, kind, identity, value,
        )

    def _decode(self, kind, identity, token, expected):
        if not isinstance(token, str):
            raise TypeError("stored engineering contract is not text")
        return decrypt_contract(
            self._cipher, self._owner_id, kind, identity, token, expected,
        )
