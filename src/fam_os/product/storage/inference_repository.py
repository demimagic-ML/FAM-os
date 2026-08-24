"""Encrypted compare-and-swap repository for restart-safe inference."""

from __future__ import annotations

import sqlite3

from fam_os.core.production import InferenceExecutionRecord
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.database import ProductionDatabase


class SqliteInferenceExecutionRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database: ProductionDatabase = database
        self._cipher: ProductPayloadCipher = cipher
        self._owner_id = owner_id

    def create(self, value: InferenceExecutionRecord) -> bool:
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO inference_executions"
                    "(instance_id,request_id,revision,state,payload_ciphertext) "
                    "VALUES (?,?,?,?,?)",
                    (
                        value.instance_id, value.request_id, value.revision,
                        value.state.value, self._encode(value),
                    ),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def get(self, instance_id: str) -> InferenceExecutionRecord | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM inference_executions WHERE instance_id=?",
            (instance_id,),
        )
        if row is None:
            return None
        token = row[0]
        if not isinstance(token, str):
            raise TypeError("stored inference payload is not text")
        value = decrypt_contract(
            self._cipher, self._owner_id, "inference-execution", instance_id,
            token, InferenceExecutionRecord,
        )
        assert isinstance(value, InferenceExecutionRecord)
        return value

    def replace(self, expected_revision: int, value: InferenceExecutionRecord) -> bool:
        if value.revision != expected_revision + 1:
            raise ValueError("inference replacement revision must advance by one")
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE inference_executions SET revision=?,state=?,payload_ciphertext=?,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE instance_id=? AND revision=?",
                (
                    value.revision, value.state.value, self._encode(value),
                    value.instance_id, expected_revision,
                ),
            )
            return cursor.rowcount == 1

    def _encode(self, value: InferenceExecutionRecord) -> str:
        return encrypt_contract(
            self._cipher, self._owner_id, "inference-execution",
            value.instance_id, value,
        )
