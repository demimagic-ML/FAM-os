"""Encrypted pinned conversion environments, approvals, and receipts."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime
from typing import TypeVar

from fam_os.expert_factory import (
    FactoryConversionApproval,
    FactoryConversionEnvironment,
    FactoryConversionReceipt,
)
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.database import ProductionDatabase


T = TypeVar("T")


class SqliteFactoryConversionRepository:
    def __init__(
        self, database: ProductionDatabase, cipher: ProductPayloadCipher,
        owner_id: str,
    ) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def add_environment(self, value: FactoryConversionEnvironment) -> bool:
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO factory_conversion_environments VALUES (?,?,?,?,?)",
                    (
                        self._owner_id, value.manifest_sha256, value.environment_id,
                        self._encrypt(
                            "factory-conversion-environment", value.manifest_sha256,
                            value,
                        ),
                        value.observed_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            existing = self.environment(value.manifest_sha256)
            if (
                existing is None
                or replace(existing, observed_at=value.observed_at) != value
            ):
                raise RuntimeError("conversion environment identity was reused") from None
            return False
        return True

    def environment(self, sha256: str) -> FactoryConversionEnvironment | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM factory_conversion_environments "
            "WHERE owner_id=? AND manifest_sha256=?", (self._owner_id, sha256),
        )
        return None if row is None else self._decrypt(
            "factory-conversion-environment", sha256, row[0],
            FactoryConversionEnvironment,
        )

    def add_approval(self, value: FactoryConversionApproval) -> bool:
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO factory_conversion_approvals VALUES "
                    "(?,?,?,?,?,?,?,1,0,?,?,?,?)",
                    (
                        self._owner_id, value.approval_id, value.evaluation_id,
                        value.comparison_decision_id, value.one_use_conversion_id,
                        value.environment_sha256, value.revision,
                        value.expires_at.isoformat(),
                        self._encrypt(
                            "factory-conversion-approval", value.approval_id, value,
                        ),
                        value.issued_at.isoformat(), value.issued_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            existing = self.approval(value.approval_id)
            if existing == value:
                return False
            if existing is not None:
                raise RuntimeError("conversion approval identity was reused") from None
            raise PermissionError("conversion requires a signed promotable decision") from None
        return True

    def approval(self, approval_id: str) -> FactoryConversionApproval | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM factory_conversion_approvals "
            "WHERE owner_id=? AND approval_id=?", (self._owner_id, approval_id),
        )
        return None if row is None else self._decrypt(
            "factory-conversion-approval", approval_id, row[0],
            FactoryConversionApproval,
        )

    def complete(
        self, receipt: FactoryConversionReceipt, consumed_at: datetime,
    ) -> None:
        self._require_receipt_lineage(receipt)
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE factory_conversion_approvals SET consumed=1,updated_at=? "
                "WHERE owner_id=? AND approval_id=? AND one_use_conversion_id=? "
                "AND active=1 AND consumed=0 AND expires_at>?",
                (
                    consumed_at.isoformat(), self._owner_id, receipt.approval_id,
                    receipt.conversion_id, consumed_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                raise PermissionError("conversion approval is unavailable or consumed")
            self._insert_receipt(connection, receipt)

    def claim(
        self, approval_id: str, conversion_id: str, revision: int,
        claimed_at: datetime,
    ) -> None:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE factory_conversion_approvals SET consumed=1,updated_at=? "
                "WHERE owner_id=? AND approval_id=? AND one_use_conversion_id=? "
                "AND revision=? AND active=1 AND consumed=0 AND expires_at>?",
                (
                    claimed_at.isoformat(), self._owner_id, approval_id,
                    conversion_id, revision, claimed_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                raise PermissionError("conversion approval is unavailable or consumed")

    def record_receipt(self, receipt: FactoryConversionReceipt) -> None:
        self._require_receipt_lineage(receipt)
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT consumed FROM factory_conversion_approvals "
                "WHERE owner_id=? AND approval_id=?",
                (self._owner_id, receipt.approval_id),
            ).fetchone()
            if row is None or row[0] != 1:
                raise PermissionError("conversion was not claimed")
            self._insert_receipt(connection, receipt)

    def receipt(self, conversion_id: str) -> FactoryConversionReceipt | None:
        row = self._database.fetchone(
            "SELECT receipt_id,payload_ciphertext FROM factory_conversion_receipts "
            "WHERE owner_id=? AND conversion_id=?", (self._owner_id, conversion_id),
        )
        return None if row is None else self._decrypt(
            "factory-conversion-receipt", row[0], row[1], FactoryConversionReceipt,
        )

    def approvals(self) -> tuple[FactoryConversionApproval, ...]:
        return self._all(
            "factory_conversion_approvals", "approval_id", "created_at",
            "factory-conversion-approval", FactoryConversionApproval,
        )

    def environments(self) -> tuple[FactoryConversionEnvironment, ...]:
        return self._all(
            "factory_conversion_environments", "manifest_sha256", "observed_at",
            "factory-conversion-environment", FactoryConversionEnvironment,
        )

    def receipts(self) -> tuple[FactoryConversionReceipt, ...]:
        return self._all(
            "factory_conversion_receipts", "receipt_id", "finished_at",
            "factory-conversion-receipt", FactoryConversionReceipt,
        )

    def _all(
        self, table: str, identifier: str, order: str, kind: str,
        expected: type[T],
    ) -> tuple[T, ...]:
        rows = self._database.fetchall(
            f"SELECT {identifier},payload_ciphertext FROM {table} "
            f"WHERE owner_id=? ORDER BY {order},{identifier}", (self._owner_id,),
        )
        return tuple(self._decrypt(kind, row[0], row[1], expected) for row in rows)

    def _encrypt(self, kind: str, identifier: str, value: object) -> str:
        return encrypt_contract(self._cipher, self._owner_id, kind, identifier, value)

    def _require_receipt_lineage(self, receipt: FactoryConversionReceipt) -> None:
        approval = self.approval(receipt.approval_id)
        if approval is None:
            raise PermissionError("conversion approval is unavailable")
        if (
            approval.one_use_conversion_id != receipt.conversion_id
            or approval.comparison_decision_sha256
            != receipt.comparison_decision_sha256
            or approval.environment_sha256 != receipt.environment_sha256
            or (
                receipt.runtime_model_ref is not None
                and approval.runtime_model_ref != receipt.runtime_model_ref
            )
        ):
            raise PermissionError("conversion receipt does not match approval")

    def _insert_receipt(
        self, connection: sqlite3.Connection,
        receipt: FactoryConversionReceipt,
    ) -> None:
        connection.execute(
            "INSERT INTO factory_conversion_receipts VALUES (?,?,?,?,?,?,?,?)",
            (
                self._owner_id, receipt.receipt_id, receipt.approval_id,
                receipt.conversion_id, receipt.status.value,
                receipt.receipt_sha256,
                self._encrypt(
                    "factory-conversion-receipt", receipt.receipt_id, receipt,
                ),
                receipt.finished_at.isoformat(),
            ),
        )

    def _decrypt(
        self, kind: str, identifier: object, token: object, expected: type[T],
    ) -> T:
        if not isinstance(identifier, str) or not isinstance(token, str):
            raise TypeError("stored conversion row is invalid")
        value = decrypt_contract(
            self._cipher, self._owner_id, kind, identifier, token, expected,
        )
        if not isinstance(value, expected):
            raise TypeError("stored conversion contract is invalid")
        return value
