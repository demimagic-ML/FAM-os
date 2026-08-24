"""Encrypted durable verifier declarations and invocation evidence."""

from __future__ import annotations

import sqlite3

from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.database import ProductionDatabase
from fam_os.verification import VerificationDeclaration, VerificationRunRecord


class SqliteVerificationRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database: ProductionDatabase = database
        self._cipher = cipher
        self._owner_id = owner_id

    def add_declaration(self, declaration: VerificationDeclaration) -> bool:
        token = encrypt_contract(
            self._cipher, self._owner_id, "verification-declaration",
            declaration.declaration_id, declaration,
        )
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO verification_declarations VALUES "
                    "(?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                    (declaration.declaration_id, declaration.request_id, token),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def declaration_for_request(self, request_id: str) -> VerificationDeclaration | None:
        row = self._database.fetchone(
            "SELECT declaration_id,payload_ciphertext FROM verification_declarations "
            "WHERE request_id=?", (request_id,),
        )
        if row is None:
            return None
        declaration_id, token = row
        if not isinstance(declaration_id, str) or not isinstance(token, str):
            raise TypeError("stored verification declaration is invalid")
        value = decrypt_contract(
            self._cipher, self._owner_id, "verification-declaration",
            declaration_id, token, VerificationDeclaration,
        )
        assert isinstance(value, VerificationDeclaration)
        if value.request_id != request_id:
            raise ValueError("verification declaration request identity changed")
        return value

    def remove_declaration(self, declaration_id: str) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM verification_declarations WHERE declaration_id=?",
                (declaration_id,),
            )
            return cursor.rowcount == 1

    def add_run(self, record: VerificationRunRecord) -> bool:
        token = encrypt_contract(
            self._cipher, self._owner_id, "verification-run",
            record.verification_id, record,
        )
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO verification_runs VALUES "
                    "(?,?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                    (
                        record.verification_id, record.request_id,
                        record.candidate_id, record.status.value, token,
                    ),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def run(self, verification_id: str) -> VerificationRunRecord | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM verification_runs WHERE verification_id=?",
            (verification_id,),
        )
        if row is None:
            return None
        token = row[0]
        if not isinstance(token, str):
            raise TypeError("stored verification run is invalid")
        value = decrypt_contract(
            self._cipher, self._owner_id, "verification-run",
            verification_id, token, VerificationRunRecord,
        )
        assert isinstance(value, VerificationRunRecord)
        return value

    def runs_for_request(self, request_id: str) -> tuple[VerificationRunRecord, ...]:
        rows = self._database.fetchall(
            "SELECT verification_id FROM verification_runs WHERE request_id=? "
            "ORDER BY created_at,verification_id", (request_id,),
        )
        values = tuple(self.run(str(row[0])) for row in rows)
        if any(value is None for value in values):
            raise RuntimeError("verification run disappeared during enumeration")
        return tuple(value for value in values if value is not None)
