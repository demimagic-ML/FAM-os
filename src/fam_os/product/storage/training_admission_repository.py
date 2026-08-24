"""Encrypted append-only training resource and admission evidence."""

from __future__ import annotations

import sqlite3

from fam_os.expert_factory import TrainingAdmissionDecision, TrainingResourceSnapshot
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqliteTrainingAdmissionRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def record(
        self, snapshot: TrainingResourceSnapshot,
        decision: TrainingAdmissionDecision,
    ) -> bool:
        if decision.snapshot_sha256 != snapshot.snapshot_sha256:
            raise ValueError("training admission does not bind its resource snapshot")
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO factory_training_resource_snapshots VALUES (?,?,?,?,?)",
                    (
                        self._owner_id, snapshot.snapshot_id,
                        snapshot.snapshot_sha256,
                        self._encrypt(
                            "factory-training-resource", snapshot.snapshot_id, snapshot,
                        ),
                        snapshot.observed_at.isoformat(),
                    ),
                )
                connection.execute(
                    "INSERT INTO factory_training_admission_decisions VALUES "
                    "(?,?,?,?,?,?,?,?)",
                    (
                        self._owner_id, decision.decision_id, decision.approval_id,
                        decision.snapshot_sha256, int(decision.admitted),
                        decision.decision_sha256,
                        self._encrypt(
                            "factory-training-admission", decision.decision_id,
                            decision,
                        ),
                        decision.decided_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            existing = self.decision(decision.decision_id)
            if existing != decision:
                raise RuntimeError("training admission identity was reused") from None
            return False
        return True

    def decision(self, decision_id: str) -> TrainingAdmissionDecision | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM factory_training_admission_decisions "
            "WHERE owner_id=? AND decision_id=?",
            (self._owner_id, decision_id),
        )
        return None if row is None else self._decrypt(
            "factory-training-admission", decision_id, row[0],
            TrainingAdmissionDecision,
        )

    def decisions(self) -> tuple[TrainingAdmissionDecision, ...]:
        rows = self._database.fetchall(
            "SELECT decision_id,payload_ciphertext "
            "FROM factory_training_admission_decisions WHERE owner_id=? "
            "ORDER BY decided_at,decision_id", (self._owner_id,),
        )
        return tuple(
            self._decrypt(
                "factory-training-admission", row[0], row[1],
                TrainingAdmissionDecision,
            )
            for row in rows
        )

    def _encrypt(self, kind: str, identifier: str, value: object) -> str:
        return encrypt_contract(self._cipher, self._owner_id, kind, identifier, value)

    def _decrypt(self, kind: str, identifier, token, expected):
        if not isinstance(identifier, str) or not isinstance(token, str):
            raise TypeError("stored training admission row is invalid")
        value = decrypt_contract(
            self._cipher, self._owner_id, kind, identifier, token, expected,
        )
        if not isinstance(value, expected):
            raise TypeError("stored training admission contract is invalid")
        return value
