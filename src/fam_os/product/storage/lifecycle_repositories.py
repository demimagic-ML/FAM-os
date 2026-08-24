"""Durable lifecycle replay and policy repositories."""

from __future__ import annotations

import sqlite3

from fam_os.core.lifecycle.attempt_contracts import AttemptBudgetPolicy
from fam_os.core.lifecycle.control_contracts import PlanDeadlinePolicy
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.database import ProductionDatabase


class SqliteReplayRegistry:
    def __init__(self, database: ProductionDatabase, kind: str) -> None:
        if not kind.strip():
            raise ValueError("replay kind must not be empty")
        self._database = database
        self._kind = kind

    def reserve(self, identifier: str) -> bool:
        return self.reserve_many((identifier,))

    def reserve_many(self, identifiers: tuple[str, ...]) -> bool:
        if not identifiers or len(set(identifiers)) != len(identifiers):
            return False
        try:
            with self._database.transaction() as connection:
                connection.executemany(
                    "INSERT INTO core_replay(reservation_kind,reservation_id) VALUES (?,?)",
                    ((self._kind, identifier) for identifier in identifiers),
                )
        except sqlite3.IntegrityError:
            return False
        return True


class SqliteAttemptReplayRegistry:
    def __init__(self, database: ProductionDatabase) -> None:
        self._registry = SqliteReplayRegistry(database, "attempt")

    def reserve(self, attempt_ids: tuple[str, ...]) -> bool:
        return self._registry.reserve_many(attempt_ids)


class SqlitePolicyRegistry:
    def __init__(
        self,
        database: ProductionDatabase,
        cipher: ProductPayloadCipher,
        owner_id: str,
        kind: str,
        value_type: type[object],
    ) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id
        self._kind = kind
        self._value_type = value_type

    def put(self, policy_id: str, value: object) -> None:
        token = encrypt_contract(
            self._cipher, self._owner_id, f"policy.{self._kind}", policy_id, value,
        )
        with self._database.transaction() as connection:
            connection.execute(
                "INSERT INTO core_policies(policy_kind,policy_id,payload_ciphertext) "
                "VALUES (?,?,?) ON CONFLICT(policy_kind,policy_id) DO UPDATE SET "
                "payload_ciphertext=excluded.payload_ciphertext,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')",
                (self._kind, policy_id, token),
            )

    def get(self, policy_id: str) -> object | None:
        row = self._database.execute(
            "SELECT payload_ciphertext FROM core_policies WHERE policy_kind=? AND policy_id=?",
            (self._kind, policy_id),
        ).fetchone()
        if row is None:
            return None
        return decrypt_contract(
            self._cipher, self._owner_id, f"policy.{self._kind}", policy_id,
            row[0], self._value_type,
        )


class SqliteAttemptPolicyRegistry(SqlitePolicyRegistry):
    def __init__(self, database, cipher, owner_id) -> None:
        super().__init__(database, cipher, owner_id, "attempt", AttemptBudgetPolicy)

    def add(self, policy: AttemptBudgetPolicy) -> None:
        self.put(policy.plan_id, policy)

    def get(self, plan_id: str) -> AttemptBudgetPolicy | None:
        value = super().get(plan_id)
        assert value is None or isinstance(value, AttemptBudgetPolicy)
        return value


class SqliteDeadlinePolicyRegistry(SqlitePolicyRegistry):
    def __init__(self, database, cipher, owner_id) -> None:
        super().__init__(database, cipher, owner_id, "deadline", PlanDeadlinePolicy)

    def add(self, policy: PlanDeadlinePolicy) -> None:
        self.put(policy.plan_id, policy)

    def get(self, plan_id: str) -> PlanDeadlinePolicy | None:
        value = super().get(plan_id)
        assert value is None or isinstance(value, PlanDeadlinePolicy)
        return value
