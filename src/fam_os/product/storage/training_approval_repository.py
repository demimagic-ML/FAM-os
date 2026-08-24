"""Encrypted one-use factory training approvals and terminal receipts."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from fam_os.expert_factory import (
    FactoryTrainingApproval,
    TrainingApprovalConsumption,
    TrainingApprovalRevocation,
)
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqliteTrainingApprovalRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def add(self, approval: FactoryTrainingApproval) -> bool:
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO factory_training_approvals VALUES "
                    "(?,?,?,?,?,?,1,0,?,?,?,?)",
                    (
                        self._owner_id, approval.approval_id, approval.proposal_id,
                        approval.sealed_dataset_id, approval.one_use_job_id,
                        approval.revision, approval.expires_at.isoformat(),
                        self._encrypt("factory-training-approval", approval.approval_id, approval),
                        approval.issued_at.isoformat(), approval.issued_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            existing = self.get(approval.approval_id)
            if existing == approval:
                return False
            if existing is not None:
                raise RuntimeError("training approval identity was reused") from None
            raise PermissionError(
                "training approval does not bind durable proposal and dataset state",
            ) from None
        return True

    def get(self, approval_id: str) -> FactoryTrainingApproval | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM factory_training_approvals "
            "WHERE owner_id=? AND approval_id=?",
            (self._owner_id, approval_id),
        )
        if row is None:
            return None
        return self._decrypt(
            "factory-training-approval", approval_id, row[0], FactoryTrainingApproval,
        )

    def approvals(self) -> tuple[FactoryTrainingApproval, ...]:
        rows = self._database.fetchall(
            "SELECT approval_id,payload_ciphertext FROM factory_training_approvals "
            "WHERE owner_id=? ORDER BY created_at,approval_id",
            (self._owner_id,),
        )
        return tuple(
            self._decrypt(
                "factory-training-approval", row[0], row[1],
                FactoryTrainingApproval,
            )
            for row in rows
        )

    def is_active(
        self, approval_id: str, expected_revision: int, now: datetime,
    ) -> bool:
        row = self._database.fetchone(
            "SELECT count(*) FROM factory_training_approvals "
            "WHERE owner_id=? AND approval_id=? AND revision=? AND active=1 "
            "AND expires_at>?",
            (self._owner_id, approval_id, expected_revision, now.isoformat()),
        )
        return row is not None and int(row[0]) == 1

    def consume(
        self, approval_id: str, job_id: str, expected_revision: int,
        consumed_at: datetime,
    ) -> TrainingApprovalConsumption:
        receipt_id = f"training-consumption-{approval_id}"
        with self._database.transaction() as connection:
            existing = connection.execute(
                "SELECT payload_ciphertext FROM factory_training_approval_receipts "
                "WHERE owner_id=? AND receipt_id=?",
                (self._owner_id, receipt_id),
            ).fetchone()
            if existing is not None:
                receipt = self._decrypt(
                    "factory-training-consumption", receipt_id, existing[0],
                    TrainingApprovalConsumption,
                )
                if receipt.job_id != job_id or receipt.approval_revision != expected_revision:
                    raise RuntimeError("training approval consumption identity was reused")
                return receipt
            cursor = connection.execute(
                "UPDATE factory_training_approvals SET consumed=1,updated_at=? "
                "WHERE owner_id=? AND approval_id=? AND one_use_job_id=? "
                "AND revision=? AND active=1 AND consumed=0 AND expires_at>?",
                (
                    consumed_at.isoformat(), self._owner_id, approval_id, job_id,
                    expected_revision, consumed_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                raise PermissionError("training approval is absent, stale, expired, revoked, or consumed")
            receipt = TrainingApprovalConsumption(
                receipt_id, approval_id, job_id, expected_revision, consumed_at,
            )
            connection.execute(
                "INSERT INTO factory_training_approval_receipts VALUES (?,?,?,?,?,?)",
                (
                    self._owner_id, receipt_id, approval_id, "consume",
                    self._encrypt("factory-training-consumption", receipt_id, receipt),
                    consumed_at.isoformat(),
                ),
            )
            return receipt

    def revoke(
        self, approval_id: str, expected_revision: int, reason_code: str,
        revoked_at: datetime,
    ) -> TrainingApprovalRevocation:
        receipt = TrainingApprovalRevocation(
            f"training-revocation-{approval_id}-{expected_revision + 1}",
            approval_id, expected_revision, expected_revision + 1, reason_code,
            revoked_at,
        )
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE factory_training_approvals SET active=0,revision=?,updated_at=? "
                "WHERE owner_id=? AND approval_id=? AND revision=? AND active=1",
                (
                    receipt.current_revision, revoked_at.isoformat(), self._owner_id,
                    approval_id, expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("training approval is absent, inactive, or changed")
            connection.execute(
                "INSERT INTO factory_training_approval_receipts VALUES (?,?,?,?,?,?)",
                (
                    self._owner_id, receipt.receipt_id, approval_id, "revoke",
                    self._encrypt(
                        "factory-training-revocation", receipt.receipt_id, receipt,
                    ),
                    revoked_at.isoformat(),
                ),
            )
        return receipt

    def consumptions(self) -> tuple[TrainingApprovalConsumption, ...]:
        return self._receipts("consume", "factory-training-consumption", TrainingApprovalConsumption)

    def revocations(self) -> tuple[TrainingApprovalRevocation, ...]:
        return self._receipts("revoke", "factory-training-revocation", TrainingApprovalRevocation)

    def _receipts(self, operation, kind, expected):
        rows = self._database.fetchall(
            "SELECT receipt_id,payload_ciphertext FROM factory_training_approval_receipts "
            "WHERE owner_id=? AND operation=? ORDER BY recorded_at,receipt_id",
            (self._owner_id, operation),
        )
        return tuple(self._decrypt(kind, row[0], row[1], expected) for row in rows)

    def _encrypt(self, kind: str, identifier: str, value: object) -> str:
        return encrypt_contract(self._cipher, self._owner_id, kind, identifier, value)

    def _decrypt(self, kind: str, identifier, token, expected):
        if not isinstance(identifier, str) or not isinstance(token, str):
            raise TypeError("stored training approval row is invalid")
        value = decrypt_contract(
            self._cipher, self._owner_id, kind, identifier, token, expected,
        )
        if not isinstance(value, expected):
            raise TypeError("stored training approval contract is invalid")
        return value
