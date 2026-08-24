"""Encrypted one-use held-out evaluation state and signed evidence."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import TypeVar

from fam_os.expert_factory import (
    ExpertComparisonDecision,
    ExpertEvaluationReport,
    FactoryEvaluationApproval,
    HeldOutAccessReceipt,
    PairedEvaluationMeasurement,
)
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.database import ProductionDatabase


T = TypeVar("T")


class SqliteFactoryEvaluationRepository:
    def __init__(
        self, database: ProductionDatabase, cipher: ProductPayloadCipher,
        owner_id: str,
    ) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def add_approval(self, approval: FactoryEvaluationApproval) -> bool:
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO factory_evaluation_approvals VALUES "
                    "(?,?,?,?,?,?,?,?,1,0,?,?,?,?)",
                    (
                        self._owner_id, approval.approval_id, approval.proposal_id,
                        approval.training_receipt_id, approval.sealed_dataset_id,
                        approval.held_out_blob_id, approval.one_use_evaluation_id,
                        approval.revision, approval.expires_at.isoformat(),
                        self._encrypt(
                            "factory-evaluation-approval", approval.approval_id,
                            approval,
                        ),
                        approval.issued_at.isoformat(), approval.issued_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            existing = self.approval(approval.approval_id)
            if existing == approval:
                return False
            if existing is not None:
                raise RuntimeError("evaluation approval identity was reused") from None
            raise PermissionError(
                "evaluation approval does not bind completed training and held-out data",
            ) from None
        return True

    def approval(self, approval_id: str) -> FactoryEvaluationApproval | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM factory_evaluation_approvals "
            "WHERE owner_id=? AND approval_id=?", (self._owner_id, approval_id),
        )
        return None if row is None else self._decrypt(
            "factory-evaluation-approval", approval_id, row[0],
            FactoryEvaluationApproval,
        )

    def approvals(self) -> tuple[FactoryEvaluationApproval, ...]:
        return self._all(
            "factory_evaluation_approvals", "approval_id", "created_at",
            "factory-evaluation-approval", FactoryEvaluationApproval,
        )

    def claim(
        self, approval_id: str, evaluation_id: str, expected_revision: int,
        claimed_at: datetime,
    ) -> None:
        with self._database.transaction() as connection:
            existing = connection.execute(
                "SELECT approval_id FROM factory_evaluation_runs "
                "WHERE owner_id=? AND evaluation_id=?",
                (self._owner_id, evaluation_id),
            ).fetchone()
            if existing is not None:
                if existing[0] != approval_id:
                    raise RuntimeError("evaluation identity was reused")
                raise PermissionError("evaluation authority was already consumed")
            cursor = connection.execute(
                "UPDATE factory_evaluation_approvals "
                "SET consumed=1,updated_at=? WHERE owner_id=? AND approval_id=? "
                "AND one_use_evaluation_id=? AND revision=? AND active=1 "
                "AND consumed=0 AND expires_at>?",
                (
                    claimed_at.isoformat(), self._owner_id, approval_id,
                    evaluation_id, expected_revision, claimed_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                raise PermissionError(
                    "evaluation approval is absent, stale, expired, or consumed",
                )
            connection.execute(
                "INSERT INTO factory_evaluation_runs VALUES (?,?,?,'claimed',?,?)",
                (
                    self._owner_id, evaluation_id, approval_id,
                    claimed_at.isoformat(), claimed_at.isoformat(),
                ),
            )

    def mark_running(self, evaluation_id: str, started_at: datetime) -> None:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE factory_evaluation_runs SET state='running',updated_at=? "
                "WHERE owner_id=? AND evaluation_id=? AND state='claimed'",
                (started_at.isoformat(), self._owner_id, evaluation_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("evaluation run is not newly claimed")

    def record_access(self, receipt: HeldOutAccessReceipt) -> bool:
        if not receipt.plaintext_discarded:
            raise ValueError("held-out plaintext must be discarded before receipt commit")
        try:
            with self._database.transaction() as connection:
                cursor = connection.execute(
                    "INSERT INTO factory_held_out_access_receipts VALUES "
                    "(?,?,?,?,?,?,?,?)",
                    (
                        self._owner_id, receipt.receipt_id, receipt.approval_id,
                        receipt.evaluation_id, receipt.held_out_blob_id,
                        receipt.receipt_sha256,
                        self._encrypt(
                            "factory-held-out-access", receipt.receipt_id, receipt,
                        ),
                        receipt.accessed_at.isoformat(),
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("held-out access receipt was not stored")
        except sqlite3.IntegrityError:
            existing = self.access_receipt(receipt.evaluation_id)
            if existing == receipt:
                return False
            raise RuntimeError("held-out access receipt identity was reused") from None
        return True

    def complete(
        self,
        measurements: tuple[PairedEvaluationMeasurement, ...],
        report: ExpertEvaluationReport,
        decision: ExpertComparisonDecision,
    ) -> None:
        if not measurements or any(
            item.evaluation_id != report.evaluation_id for item in measurements
        ):
            raise ValueError("evaluation measurements do not bind their report")
        if (
            decision.evaluation_id != report.evaluation_id
            or decision.approval_id != report.approval_id
            or decision.report_sha256 != report.report_sha256
        ):
            raise ValueError("evaluation decision does not bind its report")
        with self._database.transaction() as connection:
            state = connection.execute(
                "SELECT state FROM factory_evaluation_runs "
                "WHERE owner_id=? AND evaluation_id=? AND approval_id=?",
                (self._owner_id, report.evaluation_id, report.approval_id),
            ).fetchone()
            if state is None or state[0] != "running":
                raise RuntimeError("evaluation run is not active")
            access = connection.execute(
                "SELECT count(*) FROM factory_held_out_access_receipts "
                "WHERE owner_id=? AND evaluation_id=?",
                (self._owner_id, report.evaluation_id),
            ).fetchone()
            if access is None or int(access[0]) != 1:
                raise RuntimeError("evaluation has no held-out disposal receipt")
            access_receipt = self.access_receipt(report.evaluation_id)
            if (
                access_receipt is None
                or report.held_out_access_receipt_sha256
                != access_receipt.receipt_sha256
            ):
                raise RuntimeError("evaluation report does not bind held-out disposal")
            for ordinal, item in enumerate(measurements):
                connection.execute(
                    "INSERT INTO factory_evaluation_measurements VALUES "
                    "(?,?,?,?,?,?,?,?,?)",
                    (
                        self._owner_id, item.measurement_id, item.evaluation_id,
                        item.case_id, ordinal, item.kind.value,
                        item.measurement_sha256,
                        self._encrypt(
                            "factory-evaluation-measurement", item.measurement_id,
                            item,
                        ),
                        item.measured_at.isoformat(),
                    ),
                )
            connection.execute(
                "INSERT INTO factory_evaluation_reports VALUES (?,?,?,?,?,?,?)",
                (
                    self._owner_id, report.report_id, report.approval_id,
                    report.evaluation_id, report.report_sha256,
                    self._encrypt(
                        "factory-evaluation-report", report.report_id, report,
                    ),
                    report.finished_at.isoformat(),
                ),
            )
            connection.execute(
                "INSERT INTO factory_evaluation_decisions VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    self._owner_id, decision.decision_id, decision.approval_id,
                    decision.evaluation_id, decision.report_sha256,
                    int(decision.promotable), decision.decision_sha256,
                    self._encrypt(
                        "factory-evaluation-decision", decision.decision_id, decision,
                    ),
                    decision.decided_at.isoformat(),
                ),
            )
            connection.execute(
                "UPDATE factory_evaluation_runs SET state='terminal',updated_at=? "
                "WHERE owner_id=? AND evaluation_id=? AND state='running'",
                (
                    decision.decided_at.isoformat(), self._owner_id,
                    decision.evaluation_id,
                ),
            )

    def access_receipt(self, evaluation_id: str) -> HeldOutAccessReceipt | None:
        row = self._database.fetchone(
            "SELECT receipt_id,payload_ciphertext "
            "FROM factory_held_out_access_receipts "
            "WHERE owner_id=? AND evaluation_id=?",
            (self._owner_id, evaluation_id),
        )
        return None if row is None else self._decrypt(
            "factory-held-out-access", row[0], row[1], HeldOutAccessReceipt,
        )

    def measurements(
        self, evaluation_id: str,
    ) -> tuple[PairedEvaluationMeasurement, ...]:
        rows = self._database.fetchall(
            "SELECT measurement_id,payload_ciphertext "
            "FROM factory_evaluation_measurements "
            "WHERE owner_id=? AND evaluation_id=? ORDER BY ordinal",
            (self._owner_id, evaluation_id),
        )
        return tuple(self._decrypt(
            "factory-evaluation-measurement", row[0], row[1],
            PairedEvaluationMeasurement,
        ) for row in rows)

    def report(self, evaluation_id: str) -> ExpertEvaluationReport | None:
        row = self._database.fetchone(
            "SELECT report_id,payload_ciphertext FROM factory_evaluation_reports "
            "WHERE owner_id=? AND evaluation_id=?",
            (self._owner_id, evaluation_id),
        )
        return None if row is None else self._decrypt(
            "factory-evaluation-report", row[0], row[1], ExpertEvaluationReport,
        )

    def decision(self, evaluation_id: str) -> ExpertComparisonDecision | None:
        row = self._database.fetchone(
            "SELECT decision_id,payload_ciphertext FROM factory_evaluation_decisions "
            "WHERE owner_id=? AND evaluation_id=?",
            (self._owner_id, evaluation_id),
        )
        return None if row is None else self._decrypt(
            "factory-evaluation-decision", row[0], row[1],
            ExpertComparisonDecision,
        )

    def decisions(self) -> tuple[ExpertComparisonDecision, ...]:
        return self._all(
            "factory_evaluation_decisions", "decision_id", "decided_at",
            "factory-evaluation-decision", ExpertComparisonDecision,
        )

    def _all(
        self, table: str, identifier: str, order: str, kind: str,
        expected: type[T],
    ) -> tuple[T, ...]:
        rows = self._database.fetchall(
            f"SELECT {identifier},payload_ciphertext FROM {table} "
            f"WHERE owner_id=? ORDER BY {order},{identifier}",
            (self._owner_id,),
        )
        return tuple(self._decrypt(kind, row[0], row[1], expected) for row in rows)

    def _encrypt(self, kind: str, identifier: str, value: object) -> str:
        return encrypt_contract(self._cipher, self._owner_id, kind, identifier, value)

    def _decrypt(
        self, kind: str, identifier: object, token: object, expected: type[T],
    ) -> T:
        if not isinstance(identifier, str) or not isinstance(token, str):
            raise TypeError("stored factory evaluation row is invalid")
        value = decrypt_contract(
            self._cipher, self._owner_id, kind, identifier, token, expected,
        )
        if not isinstance(value, expected):
            raise TypeError("stored factory evaluation contract is invalid")
        return value
