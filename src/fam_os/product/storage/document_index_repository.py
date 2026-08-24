"""Owner-bound encrypted production document-index persistence."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from fam_os.memory.document_contracts import DocumentIndexApproval, IndexedDocumentChunk
from fam_os.memory.document_repository import DocumentIndexRecord
from fam_os.memory.grant_contracts import DocumentIndexGrant
from fam_os.memory.management import DocumentManagementReceipt
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.database import ProductionDatabase
from fam_os.product.storage.document_management_repository import (
    SqliteDocumentManagementStore,
)


class SqliteProductDocumentIndexRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        if not owner_id.strip():
            raise ValueError("document index repository owner must not be empty")
        self._database: ProductionDatabase = database
        self._cipher = cipher
        self._owner_id = owner_id
        self._management = SqliteDocumentManagementStore(database, cipher, owner_id)

    def add_grant(self, grant: DocumentIndexGrant) -> bool:
        self._validate_grant_owner(grant)
        token = self._encrypt("document-index-grant", grant.grant_id, grant)
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO document_index_grants VALUES "
                    "(?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                    (grant.grant_id, self._owner_id, _utc(grant.expires_at), token),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def grant(self, grant_id: str) -> DocumentIndexGrant | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM document_index_grants "
            "WHERE grant_id=? AND owner_id=?", (grant_id, self._owner_id),
        )
        if row is None:
            return None
        value = self._decrypt("document-index-grant", grant_id, row[0], DocumentIndexGrant)
        assert isinstance(value, DocumentIndexGrant)
        self._validate_grant_owner(value)
        return value

    def grants(self) -> tuple[DocumentIndexGrant, ...]:
        rows = self._database.fetchall(
            "SELECT grant_id FROM document_index_grants WHERE owner_id=? ORDER BY grant_id",
            (self._owner_id,),
        )
        values = tuple(self.grant(str(row[0])) for row in rows)
        if any(value is None for value in values):
            raise RuntimeError("document index grant disappeared during enumeration")
        return tuple(value for value in values if value is not None)

    def delete_grant(self, grant_id: str) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM document_index_grants WHERE grant_id=? AND owner_id=?",
                (grant_id, self._owner_id),
            )
        return cursor.rowcount == 1

    def purge_expired(self, now: datetime) -> tuple[str, ...]:
        cutoff = _utc(now)
        rows = self._database.fetchall(
            "SELECT grant_id FROM document_index_grants "
            "WHERE owner_id=? AND expires_at<=? ORDER BY grant_id",
            (self._owner_id, cutoff),
        )
        identifiers = tuple(str(row[0]) for row in rows)
        if identifiers:
            with self._database.transaction() as connection:
                connection.executemany(
                    "DELETE FROM document_index_grants WHERE grant_id=? AND owner_id=?",
                    ((value, self._owner_id) for value in identifiers),
                )
        return identifiers

    def add(
        self, approval: DocumentIndexApproval, chunks: tuple[IndexedDocumentChunk, ...],
    ) -> None:
        with self._database.transaction() as connection:
            self._insert(connection, approval, chunks)

    def replace(
        self, approval: DocumentIndexApproval, chunks: tuple[IndexedDocumentChunk, ...],
    ) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                "DELETE FROM document_index_documents WHERE document_id=? AND owner_id=?",
                (approval.document_id, self._owner_id),
            )
            self._insert(connection, approval, chunks)

    def replace_with_receipt(
        self, approval: DocumentIndexApproval,
        chunks: tuple[IndexedDocumentChunk, ...],
        expected_content_sha256: str,
        receipt: DocumentManagementReceipt,
    ) -> None:
        self._management.replace_document(
            approval, chunks, expected_content_sha256, receipt, self._insert,
        )

    def approval(self, document_id: str) -> DocumentIndexApproval | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM document_index_documents "
            "WHERE document_id=? AND owner_id=?", (document_id, self._owner_id),
        )
        if row is None:
            return None
        value = self._decrypt(
            "document-index-approval", document_id, row[0], DocumentIndexApproval,
        )
        assert isinstance(value, DocumentIndexApproval)
        if value.document_id != document_id or value.scope.owner_id != self._owner_id:
            raise ValueError("stored document approval identity changed")
        return value

    def chunks(self, document_id: str) -> tuple[IndexedDocumentChunk, ...]:
        rows = self._database.fetchall(
            "SELECT c.chunk_id,c.payload_ciphertext FROM document_index_chunks c "
            "JOIN document_index_documents d USING(document_id) "
            "WHERE c.document_id=? AND d.owner_id=? ORDER BY c.ordinal",
            (document_id, self._owner_id),
        )
        values = tuple(
            self._decrypt("document-index-chunk", str(row[0]), row[1], IndexedDocumentChunk)
            for row in rows
        )
        if any(not isinstance(value, IndexedDocumentChunk) for value in values):
            raise TypeError("stored document chunk has an invalid type")
        return tuple(value for value in values if isinstance(value, IndexedDocumentChunk))

    def records(self) -> tuple[DocumentIndexRecord, ...]:
        rows = self._database.fetchall(
            "SELECT document_id FROM document_index_documents "
            "WHERE owner_id=? ORDER BY document_id", (self._owner_id,),
        )
        records: list[DocumentIndexRecord] = []
        for row in rows:
            approval = self.approval(str(row[0]))
            if approval is None:
                raise RuntimeError("document disappeared during index enumeration")
            records.extend(DocumentIndexRecord(approval, chunk) for chunk in self.chunks(approval.document_id))
        return tuple(records)

    def delete(self, document_id: str) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM document_index_documents WHERE document_id=? AND owner_id=?",
                (document_id, self._owner_id),
            )
        return cursor.rowcount == 1

    def delete_with_receipt(
        self, document_id: str, expected_content_sha256: str,
        receipt: DocumentManagementReceipt,
    ) -> None:
        self._management.delete_document(document_id, expected_content_sha256, receipt)

    def expire_with_receipt(
        self, grant_id: str, receipt: DocumentManagementReceipt,
    ) -> None:
        self._management.expire_grant(grant_id, receipt)

    def receipts(self) -> tuple[DocumentManagementReceipt, ...]:
        return self._management.receipts()

    def receipt_for_request(self, request_id: str) -> DocumentManagementReceipt | None:
        return self._management.receipt_for_request(request_id)

    def document_ids(self, grant_id: str | None = None) -> tuple[str, ...]:
        statement = "SELECT document_id FROM document_index_documents WHERE owner_id=?"
        parameters: tuple[object, ...] = (self._owner_id,)
        if grant_id is not None:
            statement += " AND grant_id=?"
            parameters += (grant_id,)
        rows = self._database.fetchall(statement + " ORDER BY document_id", parameters)
        return tuple(str(row[0]) for row in rows)

    def _insert(self, connection, approval, chunks) -> None:
        grant = self._validated_grant(approval)
        approval_token = self._encrypt(
            "document-index-approval", approval.document_id, approval,
        )
        connection.execute(
            "INSERT INTO document_index_documents VALUES "
            "(?,?,?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
            (
                approval.document_id, grant.grant_id, self._owner_id,
                approval.source_sha256, _utc(approval.expires_at), approval_token,
            ),
        )
        connection.executemany(
            "INSERT INTO document_index_chunks VALUES (?,?,?,?)",
            (
                (
                    chunk.chunk_id, chunk.document_id, chunk.ordinal,
                    self._encrypt("document-index-chunk", chunk.chunk_id, chunk),
                )
                for chunk in chunks
            ),
        )

    def _validated_grant(self, approval: DocumentIndexApproval) -> DocumentIndexGrant:
        if approval.grant_id is None or approval.expires_at is None:
            raise ValueError("production document approval requires an expiring grant")
        grant = self.grant(approval.grant_id)
        if grant is None:
            raise PermissionError("document index grant does not exist")
        if (
            approval.scope != grant.scope
            or approval.embedding_model_ref != grant.embedding_model_ref
            or approval.embedding_artifact_sha256 != grant.embedding_artifact_sha256
            or approval.expires_at > grant.expires_at
            or approval.approved_at < grant.approved_at
        ):
            raise PermissionError("document approval exceeds its index grant")
        return grant

    def _validate_grant_owner(self, grant: DocumentIndexGrant) -> None:
        if grant.scope.owner_id != self._owner_id:
            raise PermissionError("document index grant owner is not this repository owner")

    def _encrypt(self, record_type: str, record_id: str, value: object) -> str:
        return encrypt_contract(self._cipher, self._owner_id, record_type, record_id, value)

    def _decrypt(self, record_type, record_id, token, expected_type):
        if not isinstance(token, str):
            raise TypeError("stored document index ciphertext is invalid")
        return decrypt_contract(
            self._cipher, self._owner_id, record_type, record_id, token, expected_type,
        )


def _utc(value: datetime | None) -> str:
    if value is None or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("document index persistence requires an aware timestamp")
    return value.astimezone(UTC).isoformat(timespec="microseconds")
