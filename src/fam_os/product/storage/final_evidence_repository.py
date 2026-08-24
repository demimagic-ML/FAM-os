"""Encrypted durable evidence lookup for final-result policy."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from fam_os.core.contracts import DegradationNotice
from fam_os.core.lifecycle.final_contracts import (
    AcceptanceEvidenceRecord,
    CandidateEvidenceRecord,
)
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.database import ProductionDatabase
from fam_os.fabric import (
    RemoteEvidenceDisposition,
    RemoteExecutionEvidence,
    RemoteVerificationOutcome,
    RemoteRecoveryEvidence,
)


class SqliteFinalEvidenceRegistry:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database: ProductionDatabase = database
        self._cipher: ProductPayloadCipher = cipher
        self._owner_id = owner_id

    def add_candidate(self, value: CandidateEvidenceRecord) -> bool:
        return self._add(
            "candidate", value.candidate_id, value, request_id=value.request_id,
        )

    def add_remote_candidate(
        self,
        candidate: CandidateEvidenceRecord,
        evidence: RemoteExecutionEvidence,
    ) -> bool:
        if (
            candidate.candidate_id != evidence.candidate_id
            or candidate.request_id != evidence.request_id
        ):
            raise ValueError("remote evidence does not bind its candidate")
        candidate_token = encrypt_contract(
            self._cipher, self._owner_id, "evidence.candidate",
            candidate.candidate_id, candidate,
        )
        evidence_token = encrypt_contract(
            self._cipher, self._owner_id, "evidence.remote_execution",
            evidence.evidence_id, evidence,
        )
        try:
            with self._database.transaction() as connection:
                existing = connection.execute(
                    "SELECT 1 FROM final_evidence "
                    "WHERE evidence_kind='remote_execution' AND request_id=?",
                    (evidence.request_id,),
                ).fetchone()
                if existing is not None:
                    raise sqlite3.IntegrityError("remote evidence request already exists")
                connection.execute(
                    "INSERT INTO final_evidence"
                    "(evidence_kind,evidence_id,payload_ciphertext,request_id) "
                    "VALUES ('candidate',?,?,?)",
                    (candidate.candidate_id, candidate_token, candidate.request_id),
                )
                connection.execute(
                    "INSERT INTO final_evidence"
                    "(evidence_kind,evidence_id,payload_ciphertext,request_id) "
                    "VALUES ('remote_execution',?,?,?)",
                    (evidence.evidence_id, evidence_token, evidence.request_id),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def add_acceptance(self, value: AcceptanceEvidenceRecord) -> bool:
        return self._add("acceptance", value.evidence_id, value)

    def add_remote_recovery(self, value: RemoteRecoveryEvidence) -> bool:
        token = encrypt_contract(
            self._cipher, self._owner_id, "evidence.remote_recovery",
            value.evidence_id, value,
        )
        try:
            with self._database.transaction() as connection:
                existing = connection.execute(
                    "SELECT 1 FROM final_evidence "
                    "WHERE evidence_kind='remote_recovery' AND request_id=?",
                    (value.request_id,),
                ).fetchone()
                if existing is not None:
                    raise sqlite3.IntegrityError("remote recovery already exists")
                connection.execute(
                    "INSERT INTO final_evidence"
                    "(evidence_kind,evidence_id,payload_ciphertext,request_id) "
                    "VALUES ('remote_recovery',?,?,?)",
                    (value.evidence_id, token, value.request_id),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def add_degradation(self, value: DegradationNotice) -> bool:
        return self._add("degradation", value.degradation_id, value)

    def candidate(self, candidate_id: str) -> CandidateEvidenceRecord | None:
        value = self._get("candidate", candidate_id, CandidateEvidenceRecord)
        assert value is None or isinstance(value, CandidateEvidenceRecord)
        return value

    def acceptance(self, evidence_id: str) -> AcceptanceEvidenceRecord | None:
        value = self._get("acceptance", evidence_id, AcceptanceEvidenceRecord)
        assert value is None or isinstance(value, AcceptanceEvidenceRecord)
        return value

    def remote_execution_for_request(
        self,
        request_id: str,
    ) -> RemoteExecutionEvidence | None:
        row = self._database.fetchone(
            "SELECT evidence_id FROM final_evidence "
            "WHERE evidence_kind='remote_execution' AND request_id=?",
            (request_id,),
        )
        if row is None:
            return None
        value = self._get("remote_execution", str(row[0]), RemoteExecutionEvidence)
        assert value is None or isinstance(value, RemoteExecutionEvidence)
        return value

    def remote_execution(self, evidence_id: str) -> RemoteExecutionEvidence | None:
        value = self._get("remote_execution", evidence_id, RemoteExecutionEvidence)
        assert value is None or isinstance(value, RemoteExecutionEvidence)
        return value

    def remote_recovery_for_request(
        self,
        request_id: str,
    ) -> RemoteRecoveryEvidence | None:
        row = self._database.fetchone(
            "SELECT evidence_id FROM final_evidence "
            "WHERE evidence_kind='remote_recovery' AND request_id=?",
            (request_id,),
        )
        if row is None:
            return None
        return self.remote_recovery(str(row[0]))

    def remote_recovery(
        self,
        evidence_id: str,
    ) -> RemoteRecoveryEvidence | None:
        value = self._get("remote_recovery", evidence_id, RemoteRecoveryEvidence)
        assert value is None or isinstance(value, RemoteRecoveryEvidence)
        return value

    def add_recovered_candidate(
        self,
        candidate: CandidateEvidenceRecord,
        finalized_at: datetime,
    ) -> bool:
        candidate_token = encrypt_contract(
            self._cipher, self._owner_id, "evidence.candidate",
            candidate.candidate_id, candidate,
        )
        try:
            with self._database.transaction() as connection:
                recovery = self._recovery_from_connection(
                    connection, candidate.request_id,
                )
                updated = recovery.recovered(candidate.candidate_id, finalized_at)
                connection.execute(
                    "INSERT INTO final_evidence"
                    "(evidence_kind,evidence_id,payload_ciphertext,request_id) "
                    "VALUES ('candidate',?,?,?)",
                    (candidate.candidate_id, candidate_token, candidate.request_id),
                )
                self._update_recovery(connection, updated)
        except sqlite3.IntegrityError:
            return False
        return True

    def fail_remote_recovery(
        self,
        request_id: str,
        finalized_at: datetime,
    ) -> RemoteRecoveryEvidence:
        with self._database.transaction() as connection:
            recovery = self._recovery_from_connection(connection, request_id)
            updated = recovery.local_failed(finalized_at)
            self._update_recovery(connection, updated)
        return updated

    def finalize_remote(
        self,
        request_id: str,
        candidate_id: str,
        disposition: RemoteEvidenceDisposition,
        verification_outcome: RemoteVerificationOutcome,
        *,
        acceptance_id: str | None,
        acceptance_evidence_id: str | None,
        verification_run_id: str | None,
        finalized_at: datetime,
    ) -> RemoteExecutionEvidence:
        with self._database.transaction() as connection:
            current = self._remote_from_connection(connection, request_id)
            if current.candidate_id != candidate_id:
                raise ValueError("remote evidence candidate changed before finalization")
            updated = current.finalize(
                disposition, verification_outcome,
                acceptance_id=acceptance_id,
                acceptance_evidence_id=acceptance_evidence_id,
                verification_run_id=verification_run_id,
                finalized_at=finalized_at,
            )
            self._update_remote(connection, updated)
        return updated

    def add_acceptance_and_finalize_remote(
        self,
        acceptance: AcceptanceEvidenceRecord,
        request_id: str,
        acceptance_id: str,
        verification_run_id: str | None,
        finalized_at: datetime,
    ) -> bool:
        token = encrypt_contract(
            self._cipher, self._owner_id, "evidence.acceptance",
            acceptance.evidence_id, acceptance,
        )
        try:
            with self._database.transaction() as connection:
                current = self._remote_from_connection(connection, request_id)
                if current.candidate_id != acceptance.candidate_id:
                    raise ValueError("remote acceptance targets another candidate")
                updated = current.finalize(
                    RemoteEvidenceDisposition.RELEASED,
                    RemoteVerificationOutcome.PASSED,
                    acceptance_id=acceptance_id,
                    acceptance_evidence_id=acceptance.evidence_id,
                    verification_run_id=verification_run_id,
                    finalized_at=finalized_at,
                )
                connection.execute(
                    "INSERT INTO final_evidence"
                    "(evidence_kind,evidence_id,payload_ciphertext,request_id) "
                    "VALUES ('acceptance',?,?,NULL)",
                    (acceptance.evidence_id, token),
                )
                self._update_remote(connection, updated)
        except sqlite3.IntegrityError:
            return False
        return True

    def degradation(self, degradation_id: str) -> DegradationNotice | None:
        value = self._get("degradation", degradation_id, DegradationNotice)
        assert value is None or isinstance(value, DegradationNotice)
        return value

    def _add(
        self,
        kind: str,
        identifier: str,
        value: object,
        request_id: str | None = None,
    ) -> bool:
        token = encrypt_contract(
            self._cipher, self._owner_id, f"evidence.{kind}", identifier, value,
        )
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO final_evidence"
                    "(evidence_kind,evidence_id,payload_ciphertext,request_id) "
                    "VALUES (?,?,?,?)",
                    (kind, identifier, token, request_id),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def _get(self, kind: str, identifier: str, expected_type: type[object]) -> object | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM final_evidence "
            "WHERE evidence_kind=? AND evidence_id=?",
            (kind, identifier),
        )
        if row is None:
            return None
        token = row[0]
        if not isinstance(token, str):
            raise TypeError("stored evidence payload is not text")
        return decrypt_contract(
            self._cipher, self._owner_id, f"evidence.{kind}", identifier,
            token, expected_type,
        )

    def _remote_from_connection(
        self,
        connection: sqlite3.Connection,
        request_id: str,
    ) -> RemoteExecutionEvidence:
        row = connection.execute(
            "SELECT evidence_id,payload_ciphertext FROM final_evidence "
            "WHERE evidence_kind='remote_execution' AND request_id=?",
            (request_id,),
        ).fetchone()
        if row is None or not isinstance(row[0], str) or not isinstance(row[1], str):
            raise KeyError("remote execution evidence is unavailable")
        value = decrypt_contract(
            self._cipher, self._owner_id, "evidence.remote_execution",
            row[0], row[1], RemoteExecutionEvidence,
        )
        assert isinstance(value, RemoteExecutionEvidence)
        return value

    def _update_remote(
        self,
        connection: sqlite3.Connection,
        value: RemoteExecutionEvidence,
    ) -> None:
        token = encrypt_contract(
            self._cipher, self._owner_id, "evidence.remote_execution",
            value.evidence_id, value,
        )
        cursor = connection.execute(
            "UPDATE final_evidence SET payload_ciphertext=? "
            "WHERE evidence_kind='remote_execution' AND evidence_id=?",
            (token, value.evidence_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("remote execution evidence disappeared")

    def _recovery_from_connection(
        self,
        connection: sqlite3.Connection,
        request_id: str,
    ) -> RemoteRecoveryEvidence:
        row = connection.execute(
            "SELECT evidence_id,payload_ciphertext FROM final_evidence "
            "WHERE evidence_kind='remote_recovery' AND request_id=?",
            (request_id,),
        ).fetchone()
        if row is None or not isinstance(row[0], str) or not isinstance(row[1], str):
            raise KeyError("remote recovery evidence is unavailable")
        value = decrypt_contract(
            self._cipher, self._owner_id, "evidence.remote_recovery",
            row[0], row[1], RemoteRecoveryEvidence,
        )
        assert isinstance(value, RemoteRecoveryEvidence)
        return value

    def _update_recovery(
        self,
        connection: sqlite3.Connection,
        value: RemoteRecoveryEvidence,
    ) -> None:
        token = encrypt_contract(
            self._cipher, self._owner_id, "evidence.remote_recovery",
            value.evidence_id, value,
        )
        cursor = connection.execute(
            "UPDATE final_evidence SET payload_ciphertext=? "
            "WHERE evidence_kind='remote_recovery' AND evidence_id=?",
            (token, value.evidence_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("remote recovery evidence disappeared")
