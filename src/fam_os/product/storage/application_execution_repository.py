"""Encrypted compare-and-swap storage for application execution state."""

import sqlite3

from fam_os.core.production.application_contracts import ApplicationExecutionRecord
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqliteApplicationExecutionRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def create(self, record: ApplicationExecutionRecord) -> bool:
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO application_executions(instance_id,request_id,revision,"
                    "state,payload_ciphertext) VALUES (?,?,?,?,?)",
                    (
                        record.instance_id, record.request_id, record.revision,
                        record.state.value, self._encode(record),
                    ),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def get(self, instance_id: str) -> ApplicationExecutionRecord | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM application_executions WHERE instance_id=?",
            (instance_id,),
        )
        if row is None:
            return None
        token = row[0]
        if not isinstance(token, str):
            raise TypeError("stored application execution payload is not text")
        value = decrypt_contract(
            self._cipher, self._owner_id, "application-execution",
            instance_id, token, ApplicationExecutionRecord,
        )
        assert isinstance(value, ApplicationExecutionRecord)
        return value

    def replace(self, expected_revision: int, record: ApplicationExecutionRecord) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE application_executions SET revision=?,state=?,payload_ciphertext=?,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE instance_id=? AND revision=?",
                (
                    record.revision, record.state.value, self._encode(record),
                    record.instance_id, expected_revision,
                ),
            )
            return cursor.rowcount == 1

    def _encode(self, record: ApplicationExecutionRecord) -> str:
        return encrypt_contract(
            self._cipher, self._owner_id, "application-execution",
            record.instance_id, record,
        )
