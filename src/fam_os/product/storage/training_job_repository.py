"""Encrypted restart-safe real training jobs and terminal evidence."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from fam_os.expert_factory import (
    AdapterTrainingJob,
    TrainingApprovalConsumption,
    TrainingBackendEnvironment,
    TrainingTerminalReceipt,
)
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqliteTrainingJobRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def add_environment(self, environment: TrainingBackendEnvironment) -> bool:
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO factory_training_environments VALUES (?,?,?,?,?,?)",
                    (
                        self._owner_id, environment.manifest_sha256,
                        environment.environment_id, int(environment.qlora_compatible),
                        self._encrypt(
                            "factory-training-environment",
                            environment.manifest_sha256, environment,
                        ),
                        environment.observed_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def environment(self, manifest_sha256: str) -> TrainingBackendEnvironment | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM factory_training_environments "
            "WHERE owner_id=? AND manifest_sha256=?",
            (self._owner_id, manifest_sha256),
        )
        return None if row is None else self._decrypt(
            "factory-training-environment", manifest_sha256, row[0],
            TrainingBackendEnvironment,
        )

    def environments(self) -> tuple[TrainingBackendEnvironment, ...]:
        rows = self._database.fetchall(
            "SELECT manifest_sha256,payload_ciphertext "
            "FROM factory_training_environments WHERE owner_id=? "
            "ORDER BY observed_at,manifest_sha256",
            (self._owner_id,),
        )
        return tuple(
            self._decrypt(
                "factory-training-environment", row[0], row[1],
                TrainingBackendEnvironment,
            )
            for row in rows
        )

    def add_job(self, job: AdapterTrainingJob) -> bool:
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO factory_training_jobs VALUES (?,?,?,?,?,?,'admitted',?,?,?)",
                    (
                        self._owner_id, job.job_id, job.approval_id, job.dataset_id,
                        job.environment_sha256, job.job_sha256,
                        self._encrypt("factory-training-job", job.job_id, job),
                        job.admitted_at.isoformat(), job.admitted_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            existing = self.get(job.job_id)
            if existing != job:
                raise RuntimeError("training job identity was reused") from None
            return False
        return True

    def admit(
        self, job: AdapterTrainingJob, consumed_at: datetime,
    ) -> TrainingApprovalConsumption:
        existing = self.get(job.job_id)
        if existing is not None:
            if existing != job:
                raise RuntimeError("training job identity was reused")
            receipt = self._consumption(job.approval_consumption_receipt_id)
            if receipt is None:
                raise RuntimeError("admitted training job has no authority receipt")
            return receipt
        receipt = TrainingApprovalConsumption(
            job.approval_consumption_receipt_id, job.approval_id, job.job_id,
            job.approval_revision, consumed_at,
        )
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE factory_training_approvals SET consumed=1,updated_at=? "
                "WHERE owner_id=? AND approval_id=? AND one_use_job_id=? "
                "AND revision=? AND active=1 AND consumed=0 AND expires_at>?",
                (
                    consumed_at.isoformat(), self._owner_id, job.approval_id,
                    job.job_id, job.approval_revision, consumed_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                raise PermissionError(
                    "training approval is absent, stale, expired, revoked, or consumed",
                )
            connection.execute(
                "INSERT INTO factory_training_approval_receipts VALUES (?,?,?,?,?,?)",
                (
                    self._owner_id, receipt.receipt_id, receipt.approval_id,
                    "consume", self._encrypt(
                        "factory-training-consumption", receipt.receipt_id, receipt,
                    ),
                    consumed_at.isoformat(),
                ),
            )
            connection.execute(
                "INSERT INTO factory_training_jobs VALUES "
                "(?,?,?,?,?,?,'admitted',?,?,?)",
                (
                    self._owner_id, job.job_id, job.approval_id, job.dataset_id,
                    job.environment_sha256, job.job_sha256,
                    self._encrypt("factory-training-job", job.job_id, job),
                    job.admitted_at.isoformat(), job.admitted_at.isoformat(),
                ),
            )
        return receipt

    def get(self, job_id: str) -> AdapterTrainingJob | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM factory_training_jobs "
            "WHERE owner_id=? AND job_id=?", (self._owner_id, job_id),
        )
        return None if row is None else self._decrypt(
            "factory-training-job", job_id, row[0], AdapterTrainingJob,
        )

    def mark_running(self, job_id: str, started_at: datetime) -> None:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE factory_training_jobs SET state='running',updated_at=? "
                "WHERE owner_id=? AND job_id=? AND state='admitted'",
                (started_at.isoformat(), self._owner_id, job_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("training job is not admitted")

    def record_terminal(self, receipt: TrainingTerminalReceipt) -> bool:
        existing = self.terminal(receipt.job_id)
        if existing is not None:
            if existing != receipt:
                raise RuntimeError("training terminal identity was reused")
            return False
        job = self.get(receipt.job_id)
        if job is None or (
            job.approval_id != receipt.approval_id
            or job.environment_sha256 != receipt.environment_sha256
        ):
            raise ValueError("training terminal receipt does not bind its job")
        try:
            with self._database.transaction() as connection:
                cursor = connection.execute(
                    "UPDATE factory_training_jobs SET state='terminal',updated_at=? "
                    "WHERE owner_id=? AND job_id=? AND state IN ('admitted','running')",
                    (receipt.finished_at.isoformat(), self._owner_id, receipt.job_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("training job is already terminal or unavailable")
                connection.execute(
                    "INSERT INTO factory_training_terminal_receipts VALUES "
                    "(?,?,?,?,?,?,?)",
                    (
                        self._owner_id, receipt.receipt_id, receipt.job_id,
                        receipt.status.value, receipt.receipt_sha256,
                        self._encrypt(
                            "factory-training-terminal", receipt.receipt_id, receipt,
                        ),
                        receipt.finished_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            existing = self.terminal(receipt.job_id)
            if existing != receipt:
                raise RuntimeError("training terminal identity was reused") from None
            return False
        return True

    def terminal(self, job_id: str) -> TrainingTerminalReceipt | None:
        row = self._database.fetchone(
            "SELECT receipt_id,payload_ciphertext "
            "FROM factory_training_terminal_receipts WHERE owner_id=? AND job_id=?",
            (self._owner_id, job_id),
        )
        return None if row is None else self._decrypt(
            "factory-training-terminal", row[0], row[1], TrainingTerminalReceipt,
        )

    def _consumption(
        self, receipt_id: str,
    ) -> TrainingApprovalConsumption | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM factory_training_approval_receipts "
            "WHERE owner_id=? AND receipt_id=? AND operation='consume'",
            (self._owner_id, receipt_id),
        )
        return None if row is None else self._decrypt(
            "factory-training-consumption", receipt_id, row[0],
            TrainingApprovalConsumption,
        )

    def jobs(self) -> tuple[AdapterTrainingJob, ...]:
        rows = self._database.fetchall(
            "SELECT job_id,payload_ciphertext FROM factory_training_jobs "
            "WHERE owner_id=? ORDER BY admitted_at,job_id", (self._owner_id,),
        )
        return tuple(
            self._decrypt("factory-training-job", row[0], row[1], AdapterTrainingJob)
            for row in rows
        )

    def terminals(self) -> tuple[TrainingTerminalReceipt, ...]:
        rows = self._database.fetchall(
            "SELECT receipt_id,payload_ciphertext "
            "FROM factory_training_terminal_receipts WHERE owner_id=? "
            "ORDER BY finished_at,receipt_id", (self._owner_id,),
        )
        return tuple(
            self._decrypt(
                "factory-training-terminal", row[0], row[1], TrainingTerminalReceipt,
            )
            for row in rows
        )

    def _encrypt(self, kind: str, identifier: str, value: object) -> str:
        return encrypt_contract(self._cipher, self._owner_id, kind, identifier, value)

    def _decrypt(self, kind: str, identifier, token, expected):
        if not isinstance(identifier, str) or not isinstance(token, str):
            raise TypeError("stored training job row is invalid")
        value = decrypt_contract(
            self._cipher, self._owner_id, kind, identifier, token, expected,
        )
        if not isinstance(value, expected):
            raise TypeError("stored training job contract is invalid")
        return value
