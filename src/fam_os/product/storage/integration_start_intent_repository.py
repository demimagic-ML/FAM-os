"""Encrypted intent-before-effect records for integration environment starts."""

from dataclasses import dataclass

from fam_os.core.engineering import (
    CandidateWorkspace, IntegrationEnvironmentPlan, IntegrationEnvironmentReceipt,
    IntegrationEnvironmentStatus, IntegrationExecutionPermit,
    integration_environment_plan_digest,
)
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


@dataclass(frozen=True, slots=True)
class StoredIntegrationStartIntent:
    plan: IntegrationEnvironmentPlan
    candidate: CandidateWorkspace
    permit: IntegrationExecutionPermit | None
    recovery_receipt: IntegrationEnvironmentReceipt | None
    state: str


class SqliteIntegrationStartIntentRepository:
    def __init__(self, database, cipher, owner_id) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def begin(self, plan, candidate) -> None:
        self._validate(plan, candidate)
        identity = plan.environment_id
        self._database.execute(
            "INSERT INTO integration_environment_start_intents"
            "(environment_id,owner_id,plan_sha256,state,plan_ciphertext,"
            "candidate_ciphertext) VALUES (?,?,?,?,?,?)",
            (
                identity, self._owner_id, integration_environment_plan_digest(plan),
                "starting", self._encode("integration-intent-plan", identity, plan),
                self._encode("integration-intent-candidate", identity, candidate),
            ),
        )

    def record_permit(self, permit) -> None:
        intent = self.required(permit.environment_id)
        if (
            intent.state != "starting" or intent.permit is not None
            or permit.approved_changeset_id != intent.plan.approved_changeset_id
            or permit.exact_host_id != intent.plan.exact_host_id
        ):
            raise PermissionError("integration start permit does not match intent")
        token = self._encode("integration-intent-permit", permit.environment_id, permit)
        cursor = self._database.execute(
            "UPDATE integration_environment_start_intents SET permit_ciphertext=?,"
            "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
            "WHERE environment_id=? AND owner_id=? AND state='starting' "
            "AND permit_ciphertext IS NULL",
            (token, permit.environment_id, self._owner_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("integration start permit state changed")

    def record_interrupted(self, environment_id) -> str:
        intent = self.required(environment_id)
        if intent.state != "starting":
            raise PermissionError("integration start intent is not starting")
        state = "prelaunch_failed" if intent.permit is None else "recovery_required"
        self._transition(environment_id, "starting", state)
        return state

    def pending(self):
        rows = self._database.fetchall(
            "SELECT environment_id FROM integration_environment_start_intents "
            "WHERE owner_id=? AND state IN ('starting','recovery_required') "
            "ORDER BY updated_at,environment_id", (self._owner_id,),
        )
        return tuple(self.required(row[0]) for row in rows)

    def list(self):
        rows = self._database.fetchall(
            "SELECT environment_id FROM integration_environment_start_intents "
            "WHERE owner_id=? ORDER BY updated_at,environment_id",
            (self._owner_id,),
        )
        return tuple(self.required(row[0]) for row in rows)

    def record_prelaunch_failed(self, environment_id) -> None:
        intent = self.required(environment_id)
        if intent.state != "starting" or intent.permit is not None:
            raise PermissionError("integration prelaunch intent is not effect-free")
        self._transition(environment_id, "starting", "prelaunch_failed")

    def record_recovery(self, environment_id, receipt) -> None:
        intent = self.required(environment_id)
        if (
            intent.state not in {"starting", "recovery_required"}
            or intent.permit is None
            or receipt.status is not IntegrationEnvironmentStatus.CLEANED
            or receipt.environment_id != environment_id
            or receipt.permit_id != intent.permit.permit_id
            or not receipt.cleanup_evidence_ids
        ):
            raise PermissionError("integration intent recovery evidence is invalid")
        token = self._encode("integration-intent-recovery", environment_id, receipt)
        cursor = self._database.execute(
            "UPDATE integration_environment_start_intents SET state='recovered',"
            "recovery_receipt_ciphertext=?,"
            "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
            "WHERE environment_id=? AND owner_id=? "
            "AND state IN ('starting','recovery_required')",
            (token, environment_id, self._owner_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("integration recovery intent state changed")

    def get(self, environment_id):
        row = self._database.fetchone(
            "SELECT owner_id,state,plan_ciphertext,candidate_ciphertext,"
            "permit_ciphertext,recovery_receipt_ciphertext "
            "FROM integration_environment_start_intents WHERE environment_id=?",
            (environment_id,),
        )
        if row is None: return None
        if row[0] != self._owner_id:
            raise PermissionError("integration start intent owner does not match")
        permit = None if row[4] is None else self._decode(
            "integration-intent-permit", environment_id, row[4],
            IntegrationExecutionPermit,
        )
        recovery = None if row[5] is None else self._decode(
            "integration-intent-recovery", environment_id, row[5],
            IntegrationEnvironmentReceipt,
        )
        return StoredIntegrationStartIntent(
            self._decode("integration-intent-plan", environment_id, row[2], IntegrationEnvironmentPlan),
            self._decode("integration-intent-candidate", environment_id, row[3], CandidateWorkspace),
            permit, recovery, row[1],
        )

    def validate_commit(self, connection, environment_id, permit) -> bool:
        row = connection.execute(
            "SELECT state,permit_ciphertext FROM integration_environment_start_intents "
            "WHERE environment_id=? AND owner_id=?", (environment_id, self._owner_id),
        ).fetchone()
        if row is None: return False
        if row[0] != "starting" or row[1] is None:
            raise PermissionError("integration start intent cannot commit")
        observed = self._decode(
            "integration-intent-permit", environment_id, row[1], IntegrationExecutionPermit,
        )
        if observed != permit:
            raise PermissionError("integration committed permit differs from intent")
        return True

    def mark_committed(self, connection, environment_id) -> None:
        connection.execute(
            "UPDATE integration_environment_start_intents SET state='committed',"
            "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
            "WHERE environment_id=? AND owner_id=?",
            (environment_id, self._owner_id),
        )

    def required(self, environment_id):
        intent = self.get(environment_id)
        if intent is None: raise KeyError("integration start intent is unavailable")
        return intent

    def _transition(self, environment_id, current, target):
        cursor = self._database.execute(
            "UPDATE integration_environment_start_intents SET state=?,"
            "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
            "WHERE environment_id=? AND owner_id=? AND state=?",
            (target, environment_id, self._owner_id, current),
        )
        if cursor.rowcount != 1: raise RuntimeError("integration intent state changed")

    @staticmethod
    def _validate(plan, candidate):
        if (
            candidate.task_id != plan.task_id or candidate.candidate_id != plan.candidate_id
            or candidate.candidate_workspace != plan.candidate_root
        ):
            raise ValueError("integration start intent identities do not match")

    def _encode(self, kind, identity, value):
        return encrypt_contract(self._cipher, self._owner_id, kind, identity, value)

    def _decode(self, kind, identity, token, expected):
        return decrypt_contract(
            self._cipher, self._owner_id, kind, identity, token, expected,
        )
