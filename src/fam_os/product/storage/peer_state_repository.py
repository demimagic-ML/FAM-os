"""Encrypted production storage for authenticated peer state and controls."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime
from uuid import uuid4

from fam_os.fabric.enrollment import PeerEnrollmentRecord, PeerEnrollmentState
from fam_os.fabric.peer_state import (
    PeerCapabilityDeclaration,
    PeerManagementOperation,
    PeerManagementReceipt,
    PeerManagementRequest,
    PeerPerformanceObservation,
    PeerPrivacyPolicyRecord,
    verify_capability_declaration,
)
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.schemas import dumps_document


class SqlitePeerStateRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        if not owner_id.strip():
            raise ValueError("peer state repository owner is invalid")
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def put_capability(
        self, enrollment_id: str, value: PeerCapabilityDeclaration,
        observed_at: datetime,
    ) -> PeerCapabilityDeclaration:
        enrollment = self._active(enrollment_id)
        if value.device_id != enrollment.approval.peer_identity.device_id:
            raise PermissionError("peer capability belongs to another device")
        verify_capability_declaration(value, enrollment.approval.peer_identity, observed_at)
        expert_hash = _digest(value.expert_id)
        token = self._encrypt("peer-capability", value.declaration_id, value)
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT declaration_id,payload_ciphertext FROM fabric_peer_capabilities "
                "WHERE enrollment_id=? AND expert_id_hash=?", (enrollment_id, expert_hash),
            ).fetchone()
            if row is not None:
                current = self._decode("peer-capability", str(row[0]), row[1], PeerCapabilityDeclaration)
                if current == value:
                    return current
                refreshed = (
                    value.revision == current.revision
                    and value.issued_at >= current.issued_at
                    and _same_capability(current, value)
                )
                if value.revision < current.revision or (
                    value.revision == current.revision and not refreshed
                ):
                    raise RuntimeError("peer capability revision did not advance")
                connection.execute(
                    "DELETE FROM fabric_peer_capabilities WHERE enrollment_id=? AND expert_id_hash=?",
                    (enrollment_id, expert_hash),
                )
            connection.execute(
                "INSERT INTO fabric_peer_capabilities"
                "(enrollment_id,declaration_id,expert_id_hash,revision,expires_at,payload_ciphertext) "
                "VALUES (?,?,?,?,?,?)",
                (enrollment_id, value.declaration_id, expert_hash, value.revision,
                 value.expires_at.isoformat(), token),
            )
        return value

    def capabilities(
        self, enrollment_id: str, observed_at: datetime,
    ) -> tuple[PeerCapabilityDeclaration, ...]:
        self._active(enrollment_id)
        rows = self._database.fetchall(
            "SELECT declaration_id,payload_ciphertext FROM fabric_peer_capabilities "
            "WHERE enrollment_id=? AND expires_at>? ORDER BY declaration_id",
            (enrollment_id, observed_at.isoformat()),
        )
        return tuple(
            self._decode("peer-capability", str(row[0]), row[1], PeerCapabilityDeclaration)
            for row in rows
        )

    def add_performance(self, value: PeerPerformanceObservation) -> bool:
        enrollment = self._active(value.enrollment_id)
        if value.peer_device_id != enrollment.approval.peer_identity.device_id:
            raise PermissionError("peer measurement belongs to another device")
        token = self._encrypt("peer-performance", value.observation_id, value)
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO fabric_peer_performance"
                "(enrollment_id,observation_id,observed_at,payload_ciphertext) VALUES (?,?,?,?)",
                (value.enrollment_id, value.observation_id, value.observed_at.isoformat(), token),
            )
            connection.execute(
                "DELETE FROM fabric_peer_performance WHERE enrollment_id=? AND observation_id IN "
                "(SELECT observation_id FROM fabric_peer_performance WHERE enrollment_id=? "
                "ORDER BY observed_at DESC,observation_id DESC LIMIT -1 OFFSET 100)",
                (value.enrollment_id, value.enrollment_id),
            )
        return cursor.rowcount == 1

    def performance(self, enrollment_id: str) -> tuple[PeerPerformanceObservation, ...]:
        self._active(enrollment_id)
        rows = self._database.fetchall(
            "SELECT observation_id,payload_ciphertext FROM fabric_peer_performance "
            "WHERE enrollment_id=? ORDER BY observed_at DESC,observation_id DESC",
            (enrollment_id,),
        )
        return tuple(
            self._decode("peer-performance", str(row[0]), row[1], PeerPerformanceObservation)
            for row in rows
        )

    def privacy(self, enrollment_id: str) -> PeerPrivacyPolicyRecord | None:
        self._active(enrollment_id)
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM fabric_peer_privacy_policies WHERE enrollment_id=?",
            (enrollment_id,),
        )
        return None if row is None else self._decode(
            "peer-privacy", enrollment_id, row[0], PeerPrivacyPolicyRecord,
        )

    def apply_control(
        self, request: PeerManagementRequest, recorded_at: datetime,
    ) -> PeerManagementReceipt:
        if request.owner_id != self._owner_id:
            raise PermissionError("peer control belongs to another owner")
        if not request.confirmed:
            raise PermissionError("peer control requires explicit confirmation")
        request_digest = hashlib.sha256(dumps_document(request).encode()).hexdigest()
        with self._database.transaction() as connection:
            existing = self._receipt_in(connection, request.request_id)
            if existing is not None:
                if existing.request_sha256 != request_digest:
                    raise ValueError("peer control request identity was reused")
                return existing
            row = connection.execute(
                "SELECT state,revision,payload_ciphertext FROM fabric_peer_enrollments "
                "WHERE enrollment_id=?", (request.enrollment_id,),
            ).fetchone()
            if row is None:
                raise KeyError("peer enrollment does not exist")
            enrollment = self._decode(
                "fabric-peer-enrollment", request.enrollment_id, row[2], PeerEnrollmentRecord,
            )
            if request.operation is PeerManagementOperation.REVOKE:
                before, after, applied = self._revoke_in(
                    connection, request, enrollment, recorded_at,
                )
            else:
                if not enrollment.active:
                    raise PermissionError("revoked peer privacy cannot be changed")
                before, after, applied = self._privacy_in(
                    connection, request, enrollment, recorded_at,
                )
            receipt = PeerManagementReceipt(
                "peer-receipt-" + uuid4().hex, request.request_id, self._owner_id,
                request.operation, request.enrollment_id, request_digest,
                before, after, applied, (request.reason_code,), recorded_at,
            )
            token = self._encrypt("peer-management-receipt", receipt.receipt_id, receipt)
            connection.execute(
                "INSERT INTO fabric_peer_management_receipts"
                "(owner_id,receipt_id,request_id,operation,enrollment_id,payload_ciphertext,recorded_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (self._owner_id, receipt.receipt_id, request.request_id,
                 request.operation.value, request.enrollment_id, token, recorded_at.isoformat()),
            )
        return receipt

    def receipts(self) -> tuple[PeerManagementReceipt, ...]:
        rows = self._database.fetchall(
            "SELECT receipt_id,payload_ciphertext FROM fabric_peer_management_receipts "
            "WHERE owner_id=? ORDER BY recorded_at,receipt_id", (self._owner_id,),
        )
        return tuple(
            self._decode("peer-management-receipt", str(row[0]), row[1], PeerManagementReceipt)
            for row in rows
        )

    def _revoke_in(self, connection, request, current, at):
        before = current.revision
        if request.expected_revision != before:
            raise RuntimeError("peer enrollment revision changed")
        if not current.active:
            return before, before, False
        updated = replace(
            current, state=PeerEnrollmentState.REVOKED, revision=before + 1,
            revoked_at=at, reason_codes=(request.reason_code,),
        )
        token = self._encrypt("fabric-peer-enrollment", request.enrollment_id, updated)
        cursor = connection.execute(
            "UPDATE fabric_peer_enrollments SET state='revoked',revision=?,payload_ciphertext=?,"
            "revoked_at=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
            "WHERE enrollment_id=? AND state='active' AND revision=?",
            (updated.revision, token, at.isoformat(), request.enrollment_id, before),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("peer enrollment revision changed")
        return before, updated.revision, True

    def _privacy_in(self, connection, request, enrollment, at):
        policy = request.privacy_policy
        assert policy is not None
        peer_id = enrollment.approval.peer_identity.device_id
        if policy.owner_id != self._owner_id or policy.allowed_device_ids != (peer_id,):
            raise PermissionError("peer privacy scope differs from enrollment")
        row = connection.execute(
            "SELECT revision FROM fabric_peer_privacy_policies WHERE enrollment_id=?",
            (request.enrollment_id,),
        ).fetchone()
        before = 0 if row is None else int(row[0])
        if request.expected_revision != before:
            raise RuntimeError("peer privacy revision changed")
        record = PeerPrivacyPolicyRecord(request.enrollment_id, peer_id, policy, before + 1, at)
        token = self._encrypt("peer-privacy", request.enrollment_id, record)
        connection.execute(
            "INSERT INTO fabric_peer_privacy_policies(enrollment_id,revision,payload_ciphertext,updated_at) "
            "VALUES (?,?,?,?) ON CONFLICT(enrollment_id) DO UPDATE SET revision=excluded.revision,"
            "payload_ciphertext=excluded.payload_ciphertext,updated_at=excluded.updated_at",
            (request.enrollment_id, record.revision, token, at.isoformat()),
        )
        return before, record.revision, True

    def _active(self, enrollment_id: str) -> PeerEnrollmentRecord:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM fabric_peer_enrollments "
            "WHERE enrollment_id=? AND state='active'", (enrollment_id,),
        )
        if row is None:
            raise KeyError("active peer enrollment does not exist")
        return self._decode(
            "fabric-peer-enrollment", enrollment_id, row[0], PeerEnrollmentRecord,
        )

    def _receipt_in(self, connection, request_id):
        row = connection.execute(
            "SELECT receipt_id,payload_ciphertext FROM fabric_peer_management_receipts "
            "WHERE owner_id=? AND request_id=?", (self._owner_id, request_id),
        ).fetchone()
        return None if row is None else self._decode(
            "peer-management-receipt", str(row[0]), row[1], PeerManagementReceipt,
        )

    def _encrypt(self, purpose, identity, value) -> str:
        return encrypt_contract(self._cipher, self._owner_id, purpose, identity, value)

    def _decode(self, purpose, identity, token, expected):
        if not isinstance(token, str):
            raise TypeError("stored peer state payload is invalid")
        return decrypt_contract(self._cipher, self._owner_id, purpose, identity, token, expected)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _same_capability(first, second) -> bool:
    return (
        first.device_id, first.expert_id, first.model_ref,
        first.capability_ids, first.maximum_context_bytes, first.manifest_sha256,
    ) == (
        second.device_id, second.expert_id, second.model_ref,
        second.capability_ids, second.maximum_context_bytes, second.manifest_sha256,
    )
