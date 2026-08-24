"""Atomic encrypted storage for owner-controlled live adaptation."""

from __future__ import annotations

import hashlib
from datetime import datetime

from fam_os.adaptation import (
    AdaptationControlOperation,
    AdaptationControlStatus,
    AdaptationHealthSample,
    AdaptationInferenceObservation,
    LiveAdaptationControlReceipt,
    LiveAdaptationControlRequest,
    LiveAdaptationControlState,
    LiveAdaptationDriftReport,
)
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqliteAdaptationControlRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def ensure_state(self, value: LiveAdaptationControlState) -> LiveAdaptationControlState:
        token = self._encrypt("adaptation-control-state", "current", value)
        self._database.execute(
            "INSERT OR IGNORE INTO adaptation_control_state"
            "(owner_id,revision,enabled,payload_ciphertext) VALUES (?,?,?,?)",
            (self._owner_id, value.revision, int(value.enabled), token),
        )
        return self.state()

    def state(self) -> LiveAdaptationControlState:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM adaptation_control_state WHERE owner_id=?",
            (self._owner_id,),
        )
        if row is None:
            raise RuntimeError("adaptation control state is not initialized")
        return self._decode("adaptation-control-state", "current", row[0], LiveAdaptationControlState)

    def receipt_for_request(self, request_id: str) -> LiveAdaptationControlReceipt | None:
        row = self._database.fetchone(
            "SELECT receipt_id,payload_ciphertext FROM adaptation_control_receipts "
            "WHERE owner_id=? AND request_id=?", (self._owner_id, request_id),
        )
        return None if row is None else self._receipt(row)

    def receipts(self) -> tuple[LiveAdaptationControlReceipt, ...]:
        rows = self._database.fetchall(
            "SELECT receipt_id,payload_ciphertext FROM adaptation_control_receipts "
            "WHERE owner_id=? ORDER BY recorded_at,receipt_id", (self._owner_id,),
        )
        return tuple(self._receipt(row) for row in rows)

    def commit(
        self, request: LiveAdaptationControlRequest,
        before: LiveAdaptationControlState, after: LiveAdaptationControlState,
        status: AdaptationControlStatus, reasons: tuple[str, ...],
    ) -> LiveAdaptationControlReceipt:
        receipt = _receipt(request, before, after, status, reasons)
        with self._database.transaction() as connection:
            existing = self._existing(connection, request.request_id)
            if existing is not None:
                return existing
            self._store_state(connection, before.revision, after, status)
            self._insert_receipt(connection, receipt)
        return receipt

    def reset(
        self, request: LiveAdaptationControlRequest, at: datetime,
    ) -> LiveAdaptationControlReceipt:
        with self._database.transaction() as connection:
            existing = self._existing(connection, request.request_id)
            if existing is not None:
                return existing
            before = self._state_in(connection)
            learning = self._count(connection, "verified_learning_outcomes")
            snapshots = self._count(connection, "live_adaptation_snapshots")
            prewarms = self._count(connection, "model_prewarm_receipts")
            connection.execute(
                "DELETE FROM verified_learning_outcomes WHERE owner_id=?", (self._owner_id,),
            )
            connection.execute(
                "DELETE FROM live_adaptation_snapshots WHERE owner_id=?", (self._owner_id,),
            )
            after = LiveAdaptationControlState(
                before.revision + 1, before.enabled, (), (), (), at,
                AdaptationControlOperation.RESET,
            )
            receipt = _receipt(
                request, before, after, AdaptationControlStatus.APPLIED,
                ("adaptation.learned_behavior_removed", "terminal.results_preserved"),
                learning, snapshots, prewarms,
            )
            self._store_state(connection, before.revision, after, receipt.status)
            self._insert_receipt(connection, receipt)
        return receipt

    def add_inference(self, value: AdaptationInferenceObservation) -> bool:
        token = self._encrypt("adaptation-inference", value.observation_id, value)
        cursor = self._database.execute(
            "INSERT OR IGNORE INTO adaptation_inference_observations"
            "(owner_id,observation_id,request_id,snapshot_id,workflow_id,payload_ciphertext) "
            "VALUES (?,?,?,?,?,?)",
            (
                self._owner_id, value.observation_id, value.request_id,
                value.snapshot_id, value.workflow_id, token,
            ),
        )
        return cursor.rowcount == 1

    def inference(self, observation_id: str) -> AdaptationInferenceObservation | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM adaptation_inference_observations "
            "WHERE owner_id=? AND observation_id=?", (self._owner_id, observation_id),
        )
        if row is None:
            return None
        return self._decode("adaptation-inference", observation_id, row[0], AdaptationInferenceObservation)

    def pending_inferences(self) -> tuple[AdaptationInferenceObservation, ...]:
        rows = self._database.fetchall(
            "SELECT observation_id,payload_ciphertext FROM adaptation_inference_observations "
            "WHERE owner_id=? ORDER BY recorded_at,observation_id", (self._owner_id,),
        )
        return tuple(
            self._decode("adaptation-inference", str(row[0]), row[1], AdaptationInferenceObservation)
            for row in rows
        )

    def finalize_health(self, value: AdaptationHealthSample) -> bool:
        token = self._encrypt("adaptation-health", value.sample_id, value)
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO adaptation_health_samples"
                "(owner_id,sample_id,observation_id,snapshot_id,workflow_id,payload_ciphertext) "
                "VALUES (?,?,?,?,?,?)",
                (
                    self._owner_id, value.sample_id, value.observation_id,
                    value.snapshot_id, value.workflow_id, token,
                ),
            )
            if cursor.rowcount == 1:
                connection.execute(
                    "DELETE FROM adaptation_inference_observations "
                    "WHERE owner_id=? AND observation_id=?",
                    (self._owner_id, value.observation_id),
                )
        return cursor.rowcount == 1

    def health(self, snapshot_id: str | None = None) -> tuple[AdaptationHealthSample, ...]:
        clause = ""
        parameters: tuple[str, ...] = (self._owner_id,)
        if snapshot_id is not None:
            clause, parameters = " AND snapshot_id=?", (self._owner_id, snapshot_id)
        rows = self._database.fetchall(
            "SELECT sample_id,payload_ciphertext FROM adaptation_health_samples "
            f"WHERE owner_id=?{clause} ORDER BY recorded_at,sample_id", parameters,
        )
        return tuple(
            self._decode("adaptation-health", str(row[0]), row[1], AdaptationHealthSample)
            for row in rows
        )

    def reports(self) -> tuple[LiveAdaptationDriftReport, ...]:
        rows = self._database.fetchall(
            "SELECT report_id,payload_ciphertext FROM adaptation_drift_reports "
            "WHERE owner_id=? ORDER BY recorded_at,report_id", (self._owner_id,),
        )
        return tuple(
            self._decode("adaptation-drift", str(row[0]), row[1], LiveAdaptationDriftReport)
            for row in rows
        )

    def commit_evaluation(
        self, report: LiveAdaptationDriftReport,
        request: LiveAdaptationControlRequest,
        before: LiveAdaptationControlState, after: LiveAdaptationControlState,
        status: AdaptationControlStatus, reasons: tuple[str, ...],
    ) -> LiveAdaptationControlReceipt:
        receipt = _receipt(request, before, after, status, reasons)
        report_token = self._encrypt("adaptation-drift", report.report_id, report)
        with self._database.transaction() as connection:
            existing = self._existing(connection, request.request_id)
            if existing is not None:
                return existing
            connection.execute(
                "INSERT INTO adaptation_drift_reports"
                "(owner_id,report_id,workflow_id,baseline_snapshot_id,"
                "candidate_snapshot_id,payload_ciphertext) VALUES (?,?,?,?,?,?)",
                (
                    self._owner_id, report.report_id, report.workflow_id,
                    report.baseline.snapshot_id, report.candidate.snapshot_id, report_token,
                ),
            )
            self._store_state(connection, before.revision, after, status)
            self._insert_receipt(connection, receipt)
        return receipt

    def _state_in(self, connection) -> LiveAdaptationControlState:
        row = connection.execute(
            "SELECT payload_ciphertext FROM adaptation_control_state WHERE owner_id=?",
            (self._owner_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("adaptation control state is not initialized")
        return self._decode("adaptation-control-state", "current", row[0], LiveAdaptationControlState)

    def _existing(self, connection, request_id: str):
        row = connection.execute(
            "SELECT receipt_id,payload_ciphertext FROM adaptation_control_receipts "
            "WHERE owner_id=? AND request_id=?", (self._owner_id, request_id),
        ).fetchone()
        return None if row is None else self._receipt(row)

    def _store_state(self, connection, revision, value, status) -> None:
        if status is not AdaptationControlStatus.APPLIED:
            return
        token = self._encrypt("adaptation-control-state", "current", value)
        cursor = connection.execute(
            "UPDATE adaptation_control_state SET revision=?,enabled=?,payload_ciphertext=?,"
            "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
            "WHERE owner_id=? AND revision=?",
            (value.revision, int(value.enabled), token, self._owner_id, revision),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("adaptation control state changed concurrently")

    def _insert_receipt(self, connection, value) -> None:
        token = self._encrypt("adaptation-control-receipt", value.receipt_id, value)
        connection.execute(
            "INSERT INTO adaptation_control_receipts"
            "(owner_id,receipt_id,request_id,operation,payload_ciphertext) VALUES (?,?,?,?,?)",
            (self._owner_id, value.receipt_id, value.request_id, value.operation.value, token),
        )

    def _count(self, connection, table: str) -> int:
        return int(connection.execute(
            f"SELECT count(*) FROM {table} WHERE owner_id=?", (self._owner_id,),
        ).fetchone()[0])

    def _receipt(self, row) -> LiveAdaptationControlReceipt:
        return self._decode(
            "adaptation-control-receipt", str(row[0]), row[1], LiveAdaptationControlReceipt,
        )

    def _encrypt(self, kind: str, identifier: str, value: object) -> str:
        return encrypt_contract(self._cipher, self._owner_id, kind, identifier, value)

    def _decode(self, kind: str, identifier: str, token, expected):
        if not isinstance(token, str):
            raise TypeError("stored adaptation control payload is not text")
        value = decrypt_contract(self._cipher, self._owner_id, kind, identifier, token, expected)
        assert isinstance(value, expected)
        return value


def _receipt(
    request, before, after, status, reasons,
    learning=0, snapshots=0, prewarms=0,
) -> LiveAdaptationControlReceipt:
    digest = hashlib.sha256(
        f"{request.request_id}\0{request.operation.value}".encode("utf-8"),
    ).hexdigest()
    return LiveAdaptationControlReceipt(
        f"adaptation-control-{digest}", request.request_id, request.operation,
        status, after.updated_at, before.revision, after,
        request.target_workflow_id, learning, snapshots, prewarms, reasons,
    )
