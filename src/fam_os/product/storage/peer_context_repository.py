"""Encrypted content-free evidence for inbound and outbound peer context."""

from fam_os.fabric.context_evidence import RemoteContextDisclosureEvidence
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqlitePeerContextRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        if not owner_id.strip():
            raise ValueError("peer context repository owner is invalid")
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def add(self, value: RemoteContextDisclosureEvidence) -> bool:
        enrollment = self._database.fetchone(
            "SELECT state FROM fabric_peer_enrollments WHERE enrollment_id=?",
            (value.enrollment_id,),
        )
        if enrollment is None or enrollment[0] != "active":
            raise PermissionError("remote context requires active enrollment")
        token = encrypt_contract(
            self._cipher, self._owner_id, "peer-context-evidence",
            value.evidence_id, value,
        )
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT evidence_id,payload_ciphertext FROM fabric_remote_context_disclosures "
                "WHERE owner_id=? AND direction=? AND request_id=?",
                (self._owner_id, value.direction.value, value.request_id),
            ).fetchone()
            if row is not None:
                current = self._decode(str(row[0]), row[1])
                if current != value:
                    raise ValueError("remote context request identity was reused")
                return False
            connection.execute(
                "INSERT INTO fabric_remote_context_disclosures"
                "(owner_id,evidence_id,request_id,enrollment_id,direction,content_sha256,"
                "payload_ciphertext,recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    self._owner_id, value.evidence_id, value.request_id,
                    value.enrollment_id, value.direction.value, value.content_sha256,
                    token, value.recorded_at.isoformat(),
                ),
            )
        return True

    def for_request(self, direction, request_id) -> RemoteContextDisclosureEvidence | None:
        row = self._database.fetchone(
            "SELECT evidence_id,payload_ciphertext FROM fabric_remote_context_disclosures "
            "WHERE owner_id=? AND direction=? AND request_id=?",
            (self._owner_id, direction.value, request_id),
        )
        return None if row is None else self._decode(str(row[0]), row[1])

    def all(self) -> tuple[RemoteContextDisclosureEvidence, ...]:
        rows = self._database.fetchall(
            "SELECT evidence_id,payload_ciphertext FROM fabric_remote_context_disclosures "
            "WHERE owner_id=? ORDER BY recorded_at,evidence_id", (self._owner_id,),
        )
        return tuple(self._decode(str(row[0]), row[1]) for row in rows)

    def _decode(self, identity, token) -> RemoteContextDisclosureEvidence:
        if not isinstance(token, str):
            raise TypeError("stored remote context evidence is invalid")
        value = decrypt_contract(
            self._cipher, self._owner_id, "peer-context-evidence",
            identity, token, RemoteContextDisclosureEvidence,
        )
        assert isinstance(value, RemoteContextDisclosureEvidence)
        return value
