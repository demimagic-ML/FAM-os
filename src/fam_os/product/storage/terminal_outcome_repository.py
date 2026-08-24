"""Atomic terminal result retention, verified learning, and content redaction."""

from __future__ import annotations

from fam_os.adaptation import VerifiedLearningOutcome
from fam_os.core.contracts import TaskRequest, TaskResult
from fam_os.core.lifecycle import AcceptanceEvidenceRecord, CandidateEvidenceRecord
from fam_os.core.production import ApplicationExecutionRecord
from fam_os.product.restart_recovery import PersistedActionRecord
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.terminal_redaction import (
    TERMINAL_CONTENT_REDACTION,
    redact_action,
    redact_application,
    redact_candidate,
    redact_request,
    redact_verification_run,
)
from fam_os.verification import VerificationRunRecord


class SqliteTerminalOutcomeRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def result(self, request_id: str) -> TaskResult | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM terminal_results "
            "WHERE request_id=? AND owner_id=?", (request_id, self._owner_id),
        )
        if row is None:
            return None
        value = self._decrypt("terminal-result", request_id, row[0], TaskResult)
        assert isinstance(value, TaskResult)
        return value

    def result_count(self) -> int:
        """Return the authoritative number of retained terminal outcomes."""
        row = self._database.fetchone(
            "SELECT COUNT(*) FROM terminal_results WHERE owner_id=?",
            (self._owner_id,),
        )
        if row is None or not isinstance(row[0], int):
            raise RuntimeError("terminal result count is unavailable")
        return row[0]

    def learning_records(self) -> tuple[VerifiedLearningOutcome, ...]:
        rows = self._database.fetchall(
            "SELECT learning_id,payload_ciphertext FROM verified_learning_outcomes "
            "WHERE owner_id=? ORDER BY recorded_at,learning_id", (self._owner_id,),
        )
        values = tuple(
            self._decrypt("verified-learning", str(row[0]), row[1], VerifiedLearningOutcome)
            for row in rows
        )
        if any(not isinstance(value, VerifiedLearningOutcome) for value in values):
            raise TypeError("stored verified learning outcome has an invalid type")
        return tuple(value for value in values if isinstance(value, VerifiedLearningOutcome))

    def finalize(
        self,
        request: TaskRequest,
        result: TaskResult,
        learning: VerifiedLearningOutcome | None,
    ) -> bool:
        if result.request_id != request.request_id:
            raise ValueError("terminal result does not match its request")
        with self._database.transaction() as connection:
            if self._stored_result(connection, request.request_id):
                return False
            current, state, token = self._current_request(connection, request.request_id)
            if current != request or state not in {"running", "terminal"}:
                raise ValueError("terminal request changed before finalization")
            if learning is not None:
                self._validate_learning(connection, result, learning)
            self._insert_result(connection, result)
            if learning is not None:
                self._insert_learning(connection, learning)
            self._redact_request(connection, current, token)
            self._redact_applications(connection, request.request_id)
            self._redact_candidates(connection, request.request_id)
            self._redact_verification_runs(connection, request.request_id)
            connection.execute(
                "DELETE FROM verification_declarations WHERE request_id=?",
                (request.request_id,),
            )
        return True

    def _validate_learning(self, connection, result, learning) -> None:
        if not result.verified or learning.candidate_evidence_id not in result.evidence_ids:
            raise ValueError("learning requires a verified released candidate")
        if learning.acceptance_evidence_id not in result.evidence_ids:
            raise ValueError("learning requires released acceptance evidence")
        row = connection.execute(
            "SELECT payload_ciphertext FROM final_evidence "
            "WHERE evidence_kind='acceptance' AND evidence_id=?",
            (learning.acceptance_evidence_id,),
        ).fetchone()
        if row is None:
            raise ValueError("learning acceptance evidence is unavailable")
        acceptance = self._decrypt(
            "evidence.acceptance", learning.acceptance_evidence_id,
            row[0], AcceptanceEvidenceRecord,
        )
        if (
            not isinstance(acceptance, AcceptanceEvidenceRecord)
            or not acceptance.passed
            or acceptance.candidate_id != learning.candidate_evidence_id
        ):
            raise ValueError("learning acceptance evidence did not pass")

    def _insert_result(self, connection, result: TaskResult) -> None:
        token = self._encrypt("terminal-result", result.request_id, result)
        connection.execute(
            "INSERT INTO terminal_results"
            "(request_id,owner_id,status,payload_ciphertext) VALUES (?,?,?,?)",
            (result.request_id, self._owner_id, result.status.value, token),
        )

    def _insert_learning(self, connection, learning: VerifiedLearningOutcome) -> None:
        token = self._encrypt("verified-learning", learning.learning_id, learning)
        connection.execute(
            "INSERT INTO verified_learning_outcomes"
            "(learning_id,owner_id,acceptance_evidence_id,payload_ciphertext) "
            "VALUES (?,?,?,?)",
            (
                learning.learning_id, self._owner_id,
                learning.acceptance_evidence_id, token,
            ),
        )

    def _redact_request(self, connection, request, token) -> None:
        redacted = redact_request(request)
        cursor = connection.execute(
            "UPDATE requests SET payload_ciphertext=?,state='terminal',"
            "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
            "WHERE request_id=? AND payload_ciphertext=?",
            (self._encrypt("request", request.request_id, redacted), request.request_id, token),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("terminal request redaction lost its compare-and-swap")

    def _redact_applications(self, connection, request_id: str) -> None:
        rows = connection.execute(
            "SELECT instance_id,revision,payload_ciphertext FROM application_executions "
            "WHERE request_id=?", (request_id,),
        ).fetchall()
        for instance_id, revision, token in rows:
            value = self._decrypt(
                "application-execution", str(instance_id), token,
                ApplicationExecutionRecord,
            )
            redacted = redact_application(value)
            connection.execute(
                "UPDATE application_executions SET revision=?,payload_ciphertext=?,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE instance_id=? AND revision=?",
                (
                    redacted.revision,
                    self._encrypt("application-execution", str(instance_id), redacted),
                    instance_id, revision,
                ),
            )
            self._redact_actions(connection, str(instance_id))

    def _redact_actions(self, connection, instance_id: str) -> None:
        rows = connection.execute(
            "SELECT action_id,payload_ciphertext FROM application_action_states "
            "WHERE plan_id=?", (instance_id,),
        ).fetchall()
        for action_id, token in rows:
            value = self._decrypt("action-state", str(action_id), token, PersistedActionRecord)
            redacted = redact_action(value)
            connection.execute(
                "UPDATE application_action_states SET payload_ciphertext=?,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE action_id=?",
                (self._encrypt("action-state", str(action_id), redacted), action_id),
            )

    def _redact_candidates(self, connection, request_id: str) -> None:
        rows = connection.execute(
            "SELECT evidence_id,payload_ciphertext FROM final_evidence "
            "WHERE evidence_kind='candidate' AND request_id=?", (request_id,),
        ).fetchall()
        for candidate_id, token in rows:
            value = self._decrypt(
                "evidence.candidate", str(candidate_id), token, CandidateEvidenceRecord,
            )
            redacted = redact_candidate(value)
            connection.execute(
                "UPDATE final_evidence SET payload_ciphertext=? "
                "WHERE evidence_kind='candidate' AND evidence_id=?",
                (self._encrypt("evidence.candidate", str(candidate_id), redacted), candidate_id),
            )

    def _redact_verification_runs(self, connection, request_id: str) -> None:
        rows = connection.execute(
            "SELECT verification_id,payload_ciphertext FROM verification_runs "
            "WHERE request_id=?", (request_id,),
        ).fetchall()
        for verification_id, token in rows:
            value = self._decrypt(
                "verification-run", str(verification_id), token, VerificationRunRecord,
            )
            redacted = redact_verification_run(value)
            connection.execute(
                "UPDATE verification_runs SET payload_ciphertext=? WHERE verification_id=?",
                (
                    self._encrypt("verification-run", str(verification_id), redacted),
                    verification_id,
                ),
            )

    def _current_request(self, connection, request_id):
        row = connection.execute(
            "SELECT state,payload_ciphertext FROM requests WHERE request_id=?",
            (request_id,),
        ).fetchone()
        if row is None:
            raise KeyError("terminal request is unavailable")
        value = self._decrypt("request", request_id, row[1], TaskRequest)
        if value.prompt == TERMINAL_CONTENT_REDACTION:
            raise RuntimeError("redacted request has no retained terminal result")
        return value, str(row[0]), row[1]

    def _stored_result(self, connection, request_id: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM terminal_results WHERE request_id=? AND owner_id=?",
            (request_id, self._owner_id),
        ).fetchone()
        return row is not None

    def _encrypt(self, kind: str, identifier: str, value: object) -> str:
        return encrypt_contract(self._cipher, self._owner_id, kind, identifier, value)

    def _decrypt(self, kind: str, identifier: str, token, expected):
        if not isinstance(token, str):
            raise TypeError("stored terminal outcome payload is not text")
        return decrypt_contract(
            self._cipher, self._owner_id, kind, identifier, token, expected,
        )
