"""Encrypted durable task-request repository."""

from __future__ import annotations

import sqlite3

from fam_os.core.contracts import TaskRequest
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.database import ProductionDatabase


class SqliteTaskRequestRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database: ProductionDatabase = database
        self._cipher: ProductPayloadCipher = cipher
        self._owner_id = owner_id

    def add(self, request: TaskRequest, state: str = "admitted") -> bool:
        if not state.strip():
            raise ValueError("request state must not be empty")
        token = encrypt_contract(
            self._cipher, self._owner_id, "request", request.request_id, request,
        )
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO requests VALUES (?,?,?,"
                    "strftime('%Y-%m-%dT%H:%M:%fZ','now'),"
                    "strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                    (request.request_id, token, state),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def get(self, request_id: str) -> TaskRequest | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM requests WHERE request_id=?", (request_id,),
        )
        if row is None:
            return None
        token = row[0]
        if not isinstance(token, str):
            raise TypeError("stored request payload is not text")
        value = decrypt_contract(
            self._cipher, self._owner_id, "request", request_id, token, TaskRequest,
        )
        assert isinstance(value, TaskRequest)
        return value

    def state(self, request_id: str) -> str | None:
        row = self._database.fetchone(
            "SELECT state FROM requests WHERE request_id=?", (request_id,),
        )
        if row is None:
            return None
        state = row[0]
        if not isinstance(state, str):
            raise TypeError("stored request state is not text")
        return state

    def update_state(self, request_id: str, expected: str, replacement: str) -> bool:
        if not expected.strip() or not replacement.strip():
            raise ValueError("request states must not be empty")
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE requests SET state=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE request_id=? AND state=?",
                (replacement, request_id, expected),
            )
            return cursor.rowcount == 1
