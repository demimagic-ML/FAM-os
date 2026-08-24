"""Transactional encrypted Core plan lifecycle repository."""

from __future__ import annotations

import sqlite3

from fam_os.core.lifecycle.contracts import PlanInstanceSnapshot
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.database import ProductionDatabase


class SqlitePlanStateRepository:
    def __init__(
        self,
        database: ProductionDatabase,
        cipher: ProductPayloadCipher,
        owner_id: str,
    ) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def create(self, snapshot: PlanInstanceSnapshot) -> bool:
        token = self._encode(snapshot)
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO plans VALUES (?,?,?,?,?,"
                    "strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                    (
                        snapshot.plan.plan_id, snapshot.plan.request_id,
                        snapshot.revision, _state(snapshot), self._plan_token(snapshot),
                    ),
                )
                connection.execute(
                    "INSERT INTO plan_snapshots(instance_id,request_id,plan_id,revision,"
                    "payload_ciphertext) VALUES (?,?,?,?,?)",
                    (
                        snapshot.instance_id, snapshot.plan.request_id,
                        snapshot.plan.plan_id, snapshot.revision, token,
                    ),
                )
                self._insert_event(connection, snapshot, snapshot.events[0])
        except sqlite3.IntegrityError:
            return False
        return True

    def get(self, instance_id: str) -> PlanInstanceSnapshot | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM plan_snapshots WHERE instance_id=?",
            (instance_id,),
        )
        if row is None:
            return None
        token = row[0]
        if not isinstance(token, str):
            raise TypeError("stored plan payload is not text")
        return self._decode(instance_id, token)

    def replace(self, expected_revision: int, snapshot: PlanInstanceSnapshot) -> bool:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT payload_ciphertext,revision FROM plan_snapshots WHERE instance_id=?",
                (snapshot.instance_id,),
            ).fetchone()
            if row is None or row[1] != expected_revision:
                return False
            current = self._decode(snapshot.instance_id, row[0])
            if not _valid_replacement(current, snapshot, expected_revision):
                return False
            cursor = connection.execute(
                "UPDATE plan_snapshots SET revision=?,payload_ciphertext=?,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE instance_id=? AND revision=?",
                (
                    snapshot.revision, self._encode(snapshot), snapshot.instance_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                return False
            connection.execute(
                "UPDATE plans SET revision=?,state=?,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE plan_id=?",
                (snapshot.revision, _state(snapshot), snapshot.plan.plan_id),
            )
            self._insert_event(connection, snapshot, snapshot.events[-1])
            return True

    def _encode(self, snapshot: PlanInstanceSnapshot) -> str:
        return encrypt_contract(
            self._cipher, self._owner_id, "plan", snapshot.instance_id, snapshot,
        )

    def _decode(self, instance_id: str, token: str) -> PlanInstanceSnapshot:
        value = decrypt_contract(
            self._cipher, self._owner_id, "plan", instance_id,
            token, PlanInstanceSnapshot,
        )
        assert isinstance(value, PlanInstanceSnapshot)
        return value

    def _plan_token(self, snapshot: PlanInstanceSnapshot) -> str:
        return encrypt_contract(
            self._cipher, self._owner_id, "execution-plan",
            snapshot.plan.plan_id, snapshot.plan,
        )

    def _insert_event(self, connection, snapshot, event) -> None:
        token = encrypt_contract(
            self._cipher, self._owner_id, "plan-event", event.event_id, event,
        )
        connection.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?,?)",
            (
                event.event_id, snapshot.plan.request_id, snapshot.plan.plan_id,
                event.revision, event.kind.value, token, event.occurred_at.isoformat(),
            ),
        )


def _valid_replacement(
    current: PlanInstanceSnapshot,
    replacement: PlanInstanceSnapshot,
    expected_revision: int,
) -> bool:
    return (
        replacement.revision == expected_revision + 1
        and replacement.plan == current.plan
        and replacement.authority_binding == current.authority_binding
    )


def _state(snapshot: PlanInstanceSnapshot) -> str:
    return "terminal" if snapshot.terminal else "active"
