"""Durable request restart classifications."""

from __future__ import annotations

from fam_os.product.request_recovery import (
    RecoverableRequestState,
    RequestRecoveryRecord,
    RequestWorkKind,
)
from fam_os.product.storage.database import ProductionDatabase


class SqliteRequestRecoveryRepository:
    def __init__(self, database: ProductionDatabase) -> None:
        self._database = database

    def put(self, record: RequestRecoveryRecord) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                "INSERT INTO request_recovery(request_id,work_kind,state) VALUES (?,?,?) "
                "ON CONFLICT(request_id) DO UPDATE SET work_kind=excluded.work_kind,"
                "state=excluded.state,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')",
                (record.request_id, record.work_kind.value, record.state.value),
            )

    def records(self) -> tuple[RequestRecoveryRecord, ...]:
        rows = self._database.execute(
            "SELECT request_id,work_kind,state FROM request_recovery ORDER BY request_id"
        ).fetchall()
        return tuple(
            RequestRecoveryRecord(
                row[0], RequestWorkKind(row[1]), RecoverableRequestState(row[2]),
            )
            for row in rows
        )
