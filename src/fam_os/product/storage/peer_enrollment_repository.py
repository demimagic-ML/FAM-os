"""Encrypted durable repository for manually approved peer enrollments."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime

from fam_os.fabric.enrollment import PeerEnrollmentRecord, PeerEnrollmentState
from fam_os.fabric.pairing import DevicePairingApproval, verify_pairing_approval
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqlitePeerEnrollmentRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        if not owner_id.strip():
            raise ValueError("peer enrollment repository owner is invalid")
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def enroll(self, approval: DevicePairingApproval) -> PeerEnrollmentRecord:
        if approval.owner_id != self._owner_id:
            raise PermissionError("peer approval belongs to another owner")
        verify_pairing_approval(approval, approval.local_identity)
        enrollment_id = _enrollment_id(approval)
        record = PeerEnrollmentRecord(
            enrollment_id, approval, PeerEnrollmentState.ACTIVE, 1, approval.approved_at,
        )
        token = self._encode(record)
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT payload_ciphertext FROM fabric_peer_enrollments WHERE enrollment_id=?",
                (enrollment_id,),
            ).fetchone()
            if row is not None:
                existing = self._decode(enrollment_id, row[0])
                if existing.approval != approval:
                    raise RuntimeError("peer enrollment identity collision")
                return existing
            connection.execute(
                "INSERT INTO fabric_peer_enrollments(enrollment_id,state,revision,"
                "payload_ciphertext,enrolled_at,revoked_at) VALUES (?,?,?,?,?,NULL)",
                (
                    enrollment_id, record.state.value, record.revision, token,
                    record.enrolled_at.isoformat(),
                ),
            )
        return record

    def get(self, enrollment_id: str) -> PeerEnrollmentRecord | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM fabric_peer_enrollments WHERE enrollment_id=?",
            (enrollment_id,),
        )
        return None if row is None else self._decode(enrollment_id, row[0])

    def active(self) -> tuple[PeerEnrollmentRecord, ...]:
        rows = self._database.fetchall(
            "SELECT enrollment_id,payload_ciphertext FROM fabric_peer_enrollments "
            "WHERE state='active' ORDER BY enrollment_id",
        )
        return tuple(self._decode(row[0], row[1]) for row in rows)

    def revoke(
        self,
        enrollment_id: str,
        *,
        expected_revision: int,
        revoked_at: datetime,
        reason_code: str,
    ) -> PeerEnrollmentRecord:
        current = self.get(enrollment_id)
        if current is None:
            raise KeyError("peer enrollment does not exist")
        if not current.active:
            return current
        updated = replace(
            current, state=PeerEnrollmentState.REVOKED,
            revision=current.revision + 1, revoked_at=revoked_at,
            reason_codes=(reason_code,),
        )
        token = self._encode(updated)
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE fabric_peer_enrollments SET state='revoked',revision=?,"
                "payload_ciphertext=?,revoked_at=?,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE enrollment_id=? AND state='active' AND revision=?",
                (
                    updated.revision, token, revoked_at.isoformat(), enrollment_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("peer enrollment revision changed")
        return updated

    def _encode(self, record: PeerEnrollmentRecord) -> str:
        return encrypt_contract(
            self._cipher, self._owner_id, "fabric-peer-enrollment",
            record.enrollment_id, record,
        )

    def _decode(self, enrollment_id: object, token: object) -> PeerEnrollmentRecord:
        if not isinstance(enrollment_id, str) or not isinstance(token, str):
            raise TypeError("stored peer enrollment fields are invalid")
        value = decrypt_contract(
            self._cipher, self._owner_id, "fabric-peer-enrollment",
            enrollment_id, token, PeerEnrollmentRecord,
        )
        assert isinstance(value, PeerEnrollmentRecord)
        return value


def _enrollment_id(approval: DevicePairingApproval) -> str:
    digest = hashlib.sha256(
        f"{approval.local_device_id}|{approval.peer_identity.device_id}".encode(),
    ).hexdigest()
    return "peer-enrollment-" + digest[:32]
