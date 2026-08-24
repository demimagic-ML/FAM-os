"""Encrypted durable requests and receipts for specialist lifecycle changes."""

from __future__ import annotations

import sqlite3
from typing import TypeVar

from fam_os.expert_factory import (
    FactorySpecialistLifecycleReceipt,
    FactorySpecialistLifecycleRequest,
)
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.database import ProductionDatabase


T = TypeVar("T")


class SqliteFactoryLifecycleRepository:
    def __init__(
        self, database: ProductionDatabase, cipher: ProductPayloadCipher,
        owner_id: str,
    ) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def begin(self, value: FactorySpecialistLifecycleRequest) -> bool:
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO factory_specialist_lifecycle_requests VALUES "
                    "(?,?,?,?,?,?, 'pending',?,?,?,?)",
                    (
                        self._owner_id, value.request_id, value.action.value,
                        value.release_id, value.target_release_id,
                        value.expected_lifecycle_revision,
                        value.request_sha256,
                        self._encrypt("factory-lifecycle-request", value.request_id, value),
                        value.issued_at.isoformat(), value.issued_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            existing = self.request(value.request_id)
            if existing == value:
                return False
            raise RuntimeError("specialist lifecycle request identity was reused") from None
        return True

    def complete(self, value: FactorySpecialistLifecycleReceipt) -> None:
        request = self.request(value.request_id)
        if request is None or (
            request.request_sha256 != value.request_sha256
            or request.action is not value.action
            or request.release_id != value.release_id
            or request.target_release_id != value.target_release_id
        ):
            raise PermissionError("specialist lifecycle receipt lineage is invalid")
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT status FROM factory_specialist_lifecycle_requests "
                "WHERE owner_id=? AND request_id=?",
                (self._owner_id, value.request_id),
            ).fetchone()
            if row is None:
                raise KeyError("specialist lifecycle request is unavailable")
            if row[0] == "completed":
                if self.receipt_for_request(value.request_id) == value:
                    return
                raise RuntimeError("specialist lifecycle request already completed")
            connection.execute(
                "INSERT INTO factory_specialist_lifecycle_receipts VALUES "
                "(?,?,?,?,?,?,?,?)",
                (
                    self._owner_id, value.receipt_id, value.request_id,
                    value.action.value, value.release_id, value.receipt_sha256,
                    self._encrypt("factory-lifecycle-receipt", value.receipt_id, value),
                    value.completed_at.isoformat(),
                ),
            )
            connection.execute(
                "UPDATE factory_specialist_lifecycle_requests "
                "SET status='completed',updated_at=? "
                "WHERE owner_id=? AND request_id=? AND status='pending'",
                (value.completed_at.isoformat(), self._owner_id, value.request_id),
            )

    def request(
        self, request_id: str,
    ) -> FactorySpecialistLifecycleRequest | None:
        return self._one(
            "factory_specialist_lifecycle_requests", "request_id", request_id,
            "factory-lifecycle-request", FactorySpecialistLifecycleRequest,
        )

    def pending(self) -> tuple[FactorySpecialistLifecycleRequest, ...]:
        rows = self._database.fetchall(
            "SELECT request_id,payload_ciphertext FROM "
            "factory_specialist_lifecycle_requests WHERE owner_id=? "
            "AND status='pending' ORDER BY created_at,request_id",
            (self._owner_id,),
        )
        return tuple(
            self._decrypt(
                "factory-lifecycle-request", row[0], row[1],
                FactorySpecialistLifecycleRequest,
            )
            for row in rows
        )

    def receipt_for_request(
        self, request_id: str,
    ) -> FactorySpecialistLifecycleReceipt | None:
        return self._one(
            "factory_specialist_lifecycle_receipts", "request_id", request_id,
            "factory-lifecycle-receipt", FactorySpecialistLifecycleReceipt,
            identifier_column="receipt_id",
        )

    def receipts(self) -> tuple[FactorySpecialistLifecycleReceipt, ...]:
        rows = self._database.fetchall(
            "SELECT receipt_id,payload_ciphertext FROM "
            "factory_specialist_lifecycle_receipts WHERE owner_id=? "
            "ORDER BY completed_at,receipt_id", (self._owner_id,),
        )
        return tuple(
            self._decrypt(
                "factory-lifecycle-receipt", row[0], row[1],
                FactorySpecialistLifecycleReceipt,
            )
            for row in rows
        )

    def _one(
        self, table: str, column: str, value: str, kind: str,
        expected: type[T], *, identifier_column: str | None = None,
    ) -> T | None:
        identifier = identifier_column or column
        row = self._database.fetchone(
            f"SELECT {identifier},payload_ciphertext FROM {table} "
            f"WHERE owner_id=? AND {column}=?", (self._owner_id, value),
        )
        return None if row is None else self._decrypt(
            kind, row[0], row[1], expected,
        )

    def _encrypt(self, kind: str, identifier: str, value: object) -> str:
        return encrypt_contract(
            self._cipher, self._owner_id, kind, identifier, value,
        )

    def _decrypt(
        self, kind: str, identifier: object, token: object, expected: type[T],
    ) -> T:
        if not isinstance(identifier, str) or not isinstance(token, str):
            raise TypeError("stored specialist lifecycle row is invalid")
        value = decrypt_contract(
            self._cipher, self._owner_id, kind, identifier, token, expected,
        )
        if not isinstance(value, expected):
            raise TypeError("stored specialist lifecycle contract is invalid")
        return value
