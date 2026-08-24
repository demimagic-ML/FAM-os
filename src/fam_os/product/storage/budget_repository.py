"""Transactional durable global repair and escalation budget ledger."""

from __future__ import annotations

import sqlite3

from fam_os.core.lifecycle.attempt_contracts import AttemptKind
from fam_os.core.lifecycle.global_budget import (
    AttemptBudgetReservation,
    GlobalAttemptBudget,
    GlobalAttemptBudgetSnapshot,
)
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.database import ProductionDatabase


class SqliteGlobalAttemptBudgetLedger:
    def __init__(self, database, cipher, owner_id: str, budget: GlobalAttemptBudget) -> None:
        self._database: ProductionDatabase = database
        self._cipher: ProductPayloadCipher = cipher
        self._owner_id = owner_id
        self.budget = budget
        self._bind_budget()

    def reserve(
        self,
        reservation: AttemptBudgetReservation,
    ) -> GlobalAttemptBudgetSnapshot | None:
        if reservation.plan_instance_id != self.budget.plan_instance_id:
            return None
        with self._database.transaction() as connection:
            current = self._snapshot(connection)
            if not _within_budget(self.budget, current, reservation):
                return None
            token = encrypt_contract(
                self._cipher, self._owner_id, "attempt-reservation",
                reservation.reservation_id, reservation,
            )
            try:
                connection.execute(
                    "INSERT INTO attempt_budget_reservations VALUES (?,?,?,?,?,?,?,"
                    "strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                    (
                        reservation.reservation_id, reservation.plan_instance_id,
                        reservation.attempt_id, reservation.kind.value,
                        reservation.reserved_tokens,
                        reservation.reserved_wall_milliseconds, token,
                    ),
                )
            except sqlite3.IntegrityError:
                return None
            return self._snapshot(connection)

    def snapshot(self) -> GlobalAttemptBudgetSnapshot:
        with self._database.transaction() as connection:
            return self._snapshot(connection)

    def reservation(self, reservation_id: str) -> AttemptBudgetReservation | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM attempt_budget_reservations "
            "WHERE plan_instance_id=? AND reservation_id=?",
            (self.budget.plan_instance_id, reservation_id),
        )
        if row is None or not isinstance(row[0], str):
            return None
        value = decrypt_contract(
            self._cipher, self._owner_id, "attempt-reservation",
            reservation_id, row[0], AttemptBudgetReservation,
        )
        assert isinstance(value, AttemptBudgetReservation)
        return value

    def _bind_budget(self) -> None:
        identifier = self.budget.plan_instance_id
        token = encrypt_contract(
            self._cipher, self._owner_id, "attempt-budget", identifier, self.budget,
        )
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT payload_ciphertext FROM global_attempt_budgets WHERE plan_instance_id=?",
                (identifier,),
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO global_attempt_budgets(plan_instance_id,payload_ciphertext) "
                    "VALUES (?,?)",
                    (identifier, token),
                )
                return
            stored = decrypt_contract(
                self._cipher, self._owner_id, "attempt-budget", identifier,
                row[0], GlobalAttemptBudget,
            )
            if stored != self.budget:
                raise ValueError("global attempt budget cannot change after binding")

    def _snapshot(self, connection) -> GlobalAttemptBudgetSnapshot:
        rows = connection.execute(
            "SELECT reservation_id,kind,reserved_tokens,reserved_wall_milliseconds "
            "FROM attempt_budget_reservations WHERE plan_instance_id=? "
            "ORDER BY reservation_id",
            (self.budget.plan_instance_id,),
        ).fetchall()
        return GlobalAttemptBudgetSnapshot(
            self.budget.plan_instance_id,
            sum(row[2] for row in rows),
            sum(row[3] for row in rows),
            sum(row[1] == AttemptKind.REPAIR.value for row in rows),
            sum(row[1] == AttemptKind.ESCALATION.value for row in rows),
            tuple(row[0] for row in rows),
        )


def _within_budget(
    budget: GlobalAttemptBudget,
    current: GlobalAttemptBudgetSnapshot,
    reservation: AttemptBudgetReservation,
) -> bool:
    repairs = current.repairs + (reservation.kind is AttemptKind.REPAIR)
    escalations = current.escalations + (reservation.kind is AttemptKind.ESCALATION)
    return (
        reservation.reserved_tokens > 0
        and reservation.reserved_wall_milliseconds > 0
        and current.consumed_tokens + reservation.reserved_tokens <= budget.maximum_tokens
        and current.consumed_wall_milliseconds + reservation.reserved_wall_milliseconds
        <= budget.maximum_wall_milliseconds
        and repairs <= budget.maximum_repairs
        and escalations <= budget.maximum_escalations
    )
