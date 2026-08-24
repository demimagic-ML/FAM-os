"""Encrypted restart-safe integration-environment lifecycle storage."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.core.engineering import (
    CandidateWorkspace,
    IntegrationEnvironmentPlan,
    IntegrationEnvironmentReceipt,
    IntegrationEnvironmentStartResult,
    IntegrationEnvironmentStatus,
    integration_environment_plan_digest,
)
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.integration_start_intent_repository import (
    SqliteIntegrationStartIntentRepository,
)


@dataclass(frozen=True, slots=True)
class StoredIntegrationEnvironment:
    plan: IntegrationEnvironmentPlan
    candidate: CandidateWorkspace
    start_result: IntegrationEnvironmentStartResult
    latest_receipt: IntegrationEnvironmentReceipt
    state: str


class SqliteIntegrationEnvironmentRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id
        self._intents = SqliteIntegrationStartIntentRepository(
            database, cipher, owner_id,
        )

    def begin_start(self, plan, candidate) -> None:
        self._intents.begin(plan, candidate)

    def record_permit(self, permit) -> None:
        self._intents.record_permit(permit)

    def record_interrupted(self, environment_id: str) -> str:
        return self._intents.record_interrupted(environment_id)

    def pending_intents(self):
        return self._intents.pending()

    def record_prelaunch_failed(self, environment_id: str) -> None:
        self._intents.record_prelaunch_failed(environment_id)

    def record_intent_recovery(
        self, environment_id: str, receipt: IntegrationEnvironmentReceipt,
    ) -> None:
        self._intents.record_recovery(environment_id, receipt)

    def intent(self, environment_id: str):
        return self._intents.get(environment_id)

    def intents(self):
        return self._intents.list()

    def put_started(
        self,
        plan: IntegrationEnvironmentPlan,
        candidate: CandidateWorkspace,
        result: IntegrationEnvironmentStartResult,
    ) -> None:
        self._validate_start(plan, candidate, result)
        state = (
            "active"
            if result.receipt.status is IntegrationEnvironmentStatus.READY
            else "failed"
        )
        identity = plan.environment_id
        values = (
            identity, self._owner_id, plan.task_id, plan.candidate_id,
            result.plan_sha256, state,
            self._encode("integration-plan", identity, plan),
            self._encode("integration-candidate", identity, candidate),
            self._encode("integration-start-result", identity, result),
            self._encode("integration-latest-receipt", identity, result.receipt),
        )
        event = self._encode(
            "integration-event-receipt", result.receipt.receipt_id, result.receipt,
        )
        with self._database.transaction() as connection:
            has_intent = self._intents.validate_commit(
                connection, identity, result.permit,
            )
            connection.execute(
                "INSERT INTO integration_environments"
                "(environment_id,owner_id,task_id,candidate_id,plan_sha256,state,"
                "plan_ciphertext,candidate_ciphertext,start_result_ciphertext,"
                "latest_receipt_ciphertext) VALUES (?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            connection.execute(
                "INSERT INTO integration_environment_events"
                "(event_id,environment_id,event_kind,receipt_ciphertext) VALUES (?,?,?,?)",
                (result.receipt.receipt_id, identity, "started", event),
            )
            if has_intent:
                self._intents.mark_committed(connection, identity)

    def get(self, environment_id: str) -> StoredIntegrationEnvironment | None:
        row = self._database.fetchone(
            "SELECT owner_id,state,plan_ciphertext,candidate_ciphertext,"
            "start_result_ciphertext,latest_receipt_ciphertext "
            "FROM integration_environments WHERE environment_id=?",
            (environment_id,),
        )
        if row is None:
            return None
        if row[0] != self._owner_id:
            raise PermissionError("integration environment owner does not match")
        return StoredIntegrationEnvironment(
            self._decode("integration-plan", environment_id, row[2], IntegrationEnvironmentPlan),
            self._decode("integration-candidate", environment_id, row[3], CandidateWorkspace),
            self._decode(
                "integration-start-result", environment_id, row[4],
                IntegrationEnvironmentStartResult,
            ),
            self._decode(
                "integration-latest-receipt", environment_id, row[5],
                IntegrationEnvironmentReceipt,
            ),
            row[1],
        )

    def active(self) -> tuple[StoredIntegrationEnvironment, ...]:
        rows = self._database.fetchall(
            "SELECT environment_id FROM integration_environments "
            "WHERE owner_id=? AND state='active' ORDER BY updated_at,environment_id",
            (self._owner_id,),
        )
        return tuple(self._required(row[0]) for row in rows)

    def for_task(self, task_id: str) -> tuple[StoredIntegrationEnvironment, ...]:
        rows = self._database.fetchall(
            "SELECT environment_id FROM integration_environments "
            "WHERE owner_id=? AND task_id=? ORDER BY updated_at,environment_id",
            (self._owner_id, task_id),
        )
        return tuple(self._required(row[0]) for row in rows)

    def record_cleanup(
        self,
        environment_id: str,
        receipt: IntegrationEnvironmentReceipt,
        *,
        reconciled: bool,
    ) -> None:
        stored = self._required(environment_id)
        if (
            stored.state != "active"
            or receipt.status is not IntegrationEnvironmentStatus.CLEANED
            or receipt.environment_id != environment_id
            or receipt.permit_id != stored.start_result.permit.permit_id
        ):
            raise PermissionError("integration cleanup evidence does not match active state")
        latest = self._encode(
            "integration-latest-receipt", environment_id, receipt,
        )
        event = self._encode(
            "integration-event-receipt", receipt.receipt_id, receipt,
        )
        kind = "reconciled" if reconciled else "cleaned"
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE integration_environments SET state='cleaned',"
                "latest_receipt_ciphertext=?,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE environment_id=? AND owner_id=? AND state='active'",
                (latest, environment_id, self._owner_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("integration environment state changed during cleanup")
            connection.execute(
                "INSERT INTO integration_environment_events"
                "(event_id,environment_id,event_kind,receipt_ciphertext) VALUES (?,?,?,?)",
                (receipt.receipt_id, environment_id, kind, event),
            )

    def receipts(self, environment_id: str) -> tuple[IntegrationEnvironmentReceipt, ...]:
        self._required(environment_id)
        rows = self._database.fetchall(
            "SELECT event_id,receipt_ciphertext FROM integration_environment_events "
            "WHERE environment_id=? ORDER BY sequence", (environment_id,),
        )
        return tuple(
            self._decode(
                "integration-event-receipt", row[0], row[1],
                IntegrationEnvironmentReceipt,
            )
            for row in rows
        )

    def _required(self, environment_id: str) -> StoredIntegrationEnvironment:
        stored = self.get(environment_id)
        if stored is None:
            raise KeyError("integration environment is unavailable")
        return stored

    @staticmethod
    def _validate_start(plan, candidate, result) -> None:
        if (
            result.environment_id != plan.environment_id
            or result.plan_sha256 != integration_environment_plan_digest(plan)
            or result.receipt.status not in {
                IntegrationEnvironmentStatus.READY,
                IntegrationEnvironmentStatus.FAILED,
            }
            or candidate.task_id != plan.task_id
            or candidate.candidate_id != plan.candidate_id
            or candidate.candidate_workspace != plan.candidate_root
        ):
            raise ValueError("integration start persistence identities do not match")

    def _encode(self, kind, identity, value) -> str:
        return encrypt_contract(self._cipher, self._owner_id, kind, identity, value)

    def _decode(self, kind, identity, token, expected):
        if not isinstance(token, str):
            raise TypeError("stored integration contract is not text")
        return decrypt_contract(
            self._cipher, self._owner_id, kind, identity, token, expected,
        )
