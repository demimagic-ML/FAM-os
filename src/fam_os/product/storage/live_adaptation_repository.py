"""Owner-encrypted durable live-prediction snapshots and prewarm receipts."""

from __future__ import annotations

from fam_os.adaptation import LiveAdaptationSnapshot, ModelPrewarmReceipt
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqliteLiveAdaptationRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def add_snapshot(self, snapshot: LiveAdaptationSnapshot) -> bool:
        token = self._encrypt("live-adaptation", snapshot.snapshot_id, snapshot)
        cursor = self._database.execute(
            "INSERT OR IGNORE INTO live_adaptation_snapshots"
            "(owner_id,snapshot_id,workflow_id,payload_ciphertext) VALUES (?,?,?,?)",
            (self._owner_id, snapshot.snapshot_id, snapshot.workflow_id, token),
        )
        return cursor.rowcount == 1

    def latest(self, workflow_id: str) -> LiveAdaptationSnapshot | None:
        row = self._database.fetchone(
            "SELECT snapshot_id,payload_ciphertext FROM live_adaptation_snapshots "
            "WHERE owner_id=? AND workflow_id=? "
            "ORDER BY recorded_at DESC,snapshot_id DESC LIMIT 1",
            (self._owner_id, workflow_id),
        )
        if row is None:
            return None
        value = self._decrypt("live-adaptation", str(row[0]), row[1], LiveAdaptationSnapshot)
        assert isinstance(value, LiveAdaptationSnapshot)
        return value

    def get(self, snapshot_id: str) -> LiveAdaptationSnapshot | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM live_adaptation_snapshots "
            "WHERE owner_id=? AND snapshot_id=?", (self._owner_id, snapshot_id),
        )
        if row is None:
            return None
        value = self._decrypt(
            "live-adaptation", snapshot_id, row[0], LiveAdaptationSnapshot,
        )
        assert isinstance(value, LiveAdaptationSnapshot)
        return value

    def snapshots(self) -> tuple[LiveAdaptationSnapshot, ...]:
        rows = self._database.fetchall(
            "SELECT snapshot_id,payload_ciphertext FROM live_adaptation_snapshots "
            "WHERE owner_id=? ORDER BY recorded_at,snapshot_id", (self._owner_id,),
        )
        return tuple(self._snapshot(row) for row in rows)

    def add_receipt(self, receipt: ModelPrewarmReceipt) -> bool:
        token = self._encrypt("model-prewarm", receipt.receipt_id, receipt)
        cursor = self._database.execute(
            "INSERT OR IGNORE INTO model_prewarm_receipts"
            "(owner_id,receipt_id,snapshot_id,payload_ciphertext) VALUES (?,?,?,?)",
            (self._owner_id, receipt.receipt_id, receipt.snapshot_id, token),
        )
        return cursor.rowcount == 1

    def receipts(self) -> tuple[ModelPrewarmReceipt, ...]:
        rows = self._database.fetchall(
            "SELECT receipt_id,payload_ciphertext FROM model_prewarm_receipts "
            "WHERE owner_id=? ORDER BY recorded_at,receipt_id", (self._owner_id,),
        )
        return tuple(self._receipt(row) for row in rows)

    def _snapshot(self, row) -> LiveAdaptationSnapshot:
        value = self._decrypt(
            "live-adaptation", str(row[0]), row[1], LiveAdaptationSnapshot,
        )
        assert isinstance(value, LiveAdaptationSnapshot)
        return value

    def _receipt(self, row) -> ModelPrewarmReceipt:
        value = self._decrypt("model-prewarm", str(row[0]), row[1], ModelPrewarmReceipt)
        assert isinstance(value, ModelPrewarmReceipt)
        return value

    def _encrypt(self, kind: str, identifier: str, value: object) -> str:
        return encrypt_contract(self._cipher, self._owner_id, kind, identifier, value)

    def _decrypt(self, kind: str, identifier: str, token, expected):
        if not isinstance(token, str):
            raise TypeError("stored live adaptation payload is not text")
        return decrypt_contract(
            self._cipher, self._owner_id, kind, identifier, token, expected,
        )
