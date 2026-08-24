"""Transactional persisted application-action state."""

from __future__ import annotations

import sqlite3

from fam_os.product.restart_recovery import PersistedActionRecord, PersistedActionState
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.database import ProductionDatabase


class SqliteActionStateRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database: ProductionDatabase = database
        self._cipher: ProductPayloadCipher = cipher
        self._owner_id = owner_id

    def create(self, record: PersistedActionRecord) -> bool:
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO application_action_states(action_id,plan_id,capability_id,state,"
                    "idempotency_key,payload_ciphertext,updated_at) VALUES (?,?,?,?,?,?,"
                    "strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                    (
                        record.action_id, record.plan_id,
                        record.proposal.request.capability_id, record.state.value,
                        record.idempotency_key, self._encode(record),
                    ),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def get(self, action_id: str) -> PersistedActionRecord | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM application_action_states WHERE action_id=?",
            (action_id,),
        )
        return None if row is None else self._decode(action_id, row[0])

    def replace(
        self,
        expected: PersistedActionState,
        record: PersistedActionRecord,
    ) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE application_action_states SET state=?,payload_ciphertext=?,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE action_id=? AND state=?",
                (record.state.value, self._encode(record), record.action_id, expected.value),
            )
            return cursor.rowcount == 1

    def recoverable(self) -> tuple[PersistedActionRecord, ...]:
        terminal = tuple(item.value for item in (
            PersistedActionState.VERIFIED,
            PersistedActionState.FAILED,
            PersistedActionState.CANCELLED,
        ))
        placeholders = ",".join("?" for _ in terminal)
        rows = self._database.fetchall(
            f"SELECT action_id,payload_ciphertext FROM application_action_states "
            f"WHERE state NOT IN ({placeholders}) ORDER BY action_id",
            terminal,
        )
        return tuple(self._decode(row[0], row[1]) for row in rows)

    def awaiting_reapproval(self, proposal_id: str) -> bool:
        record = self.get(f"action-{proposal_id}")
        return (
            record is not None
            and record.proposal.proposal_id == proposal_id
            and record.state is PersistedActionState.AWAITING_APPROVAL
            and record.confirmation_id is None
        )

    def approved_confirmation(self, proposal_id: str, confirmation_id: str) -> bool:
        record = self.get(f"action-{proposal_id}")
        return (
            record is not None
            and record.proposal.proposal_id == proposal_id
            and record.state in {
                PersistedActionState.APPROVED,
                PersistedActionState.INVOKING,
            }
            and record.confirmation_id == confirmation_id
        )

    def _encode(self, record: PersistedActionRecord) -> str:
        return encrypt_contract(
            self._cipher, self._owner_id, "action-state", record.action_id, record,
        )

    def _decode(self, action_id: object, token: object) -> PersistedActionRecord:
        if not isinstance(action_id, str) or not isinstance(token, str):
            raise TypeError("stored action state has invalid fields")
        value = decrypt_contract(
            self._cipher, self._owner_id, "action-state", action_id,
            token, PersistedActionRecord,
        )
        assert isinstance(value, PersistedActionRecord)
        return value
