"""Revision-bound owner capture grants and revocation receipts."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from fam_os.expert_factory.dataset_provenance import (
    TrainingCaptureGrant,
    TrainingCaptureRevocation,
)
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqliteCaptureGrantRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def add(self, grant: TrainingCaptureGrant) -> bool:
        token = self._encrypt("factory-capture-grant", grant.grant_id, grant)
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO factory_capture_grants VALUES "
                    "(?,?,?,?,1,?,?,?,?,?,?)",
                    (
                        self._owner_id, grant.grant_id, grant.proposal_id,
                        grant.revision, grant.expires_at.isoformat(),
                        grant.maximum_source_bytes, grant.maximum_examples, token,
                        grant.issued_at.isoformat(), grant.issued_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def get(self, grant_id: str) -> TrainingCaptureGrant | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM factory_capture_grants "
            "WHERE owner_id=? AND grant_id=?",
            (self._owner_id, grant_id),
        )
        if row is None:
            return None
        return self._decrypt(
            "factory-capture-grant", grant_id, row[0], TrainingCaptureGrant,
        )

    def active(self, grant_id: str, now: datetime) -> TrainingCaptureGrant | None:
        row = self._database.fetchone(
            "SELECT revision,active,expires_at,payload_ciphertext "
            "FROM factory_capture_grants WHERE owner_id=? AND grant_id=?",
            (self._owner_id, grant_id),
        )
        if row is None or int(row[1]) != 1 or datetime.fromisoformat(str(row[2])) <= now:
            return None
        grant = self._decrypt(
            "factory-capture-grant", grant_id, row[3], TrainingCaptureGrant,
        )
        if grant.revision != int(row[0]):
            raise ValueError("capture grant revision metadata changed")
        return grant

    def revoke(
        self, grant_id: str, expected_revision: int, reason_code: str,
        revoked_at: datetime,
    ) -> TrainingCaptureRevocation:
        receipt = TrainingCaptureRevocation(
            f"capture-revocation-{grant_id}-{expected_revision + 1}",
            grant_id, expected_revision, expected_revision + 1, reason_code,
            revoked_at,
        )
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE factory_capture_grants SET active=0,revision=?,updated_at=? "
                "WHERE owner_id=? AND grant_id=? AND revision=? AND active=1",
                (
                    receipt.current_revision, revoked_at.isoformat(), self._owner_id,
                    grant_id, expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("capture grant is absent, inactive, or changed")
            connection.execute(
                "INSERT INTO factory_capture_revocations VALUES (?,?,?,?,?)",
                (
                    self._owner_id, receipt.receipt_id, grant_id,
                    self._encrypt(
                        "factory-capture-revocation", receipt.receipt_id, receipt,
                    ),
                    revoked_at.isoformat(),
                ),
            )
        return receipt

    def revocations(self) -> tuple[TrainingCaptureRevocation, ...]:
        rows = self._database.fetchall(
            "SELECT receipt_id,payload_ciphertext FROM factory_capture_revocations "
            "WHERE owner_id=? ORDER BY recorded_at,receipt_id",
            (self._owner_id,),
        )
        return tuple(
            self._decrypt(
                "factory-capture-revocation", row[0], row[1],
                TrainingCaptureRevocation,
            )
            for row in rows
        )

    def _encrypt(self, kind: str, identifier: str, value: object) -> str:
        return encrypt_contract(self._cipher, self._owner_id, kind, identifier, value)

    def _decrypt(self, kind: str, identifier, token, expected):
        if not isinstance(identifier, str) or not isinstance(token, str):
            raise TypeError("stored capture grant row is invalid")
        value = decrypt_contract(
            self._cipher, self._owner_id, kind, identifier, token, expected,
        )
        if not isinstance(value, expected):
            raise TypeError("stored capture grant contract is invalid")
        return value
