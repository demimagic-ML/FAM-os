"""Atomic encrypted document-management transitions and durable receipts."""

from __future__ import annotations

import hashlib

from fam_os.memory import DocumentManagementReceipt
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqliteDocumentManagementStore:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def replace_document(
        self, approval, chunks, expected_digest: str,
        receipt: DocumentManagementReceipt, insert_document,
    ) -> None:
        self._validate_receipt(receipt)
        if (
            receipt.target_id != approval.document_id
            or receipt.previous_content_sha256 != expected_digest
            or receipt.resulting_content_sha256 != approval.source_sha256
        ):
            raise ValueError("correction receipt does not match document transition")
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM document_index_documents "
                "WHERE document_id=? AND owner_id=? AND source_sha256=?",
                (approval.document_id, self._owner_id, expected_digest),
            )
            if cursor.rowcount != 1:
                raise ValueError("document changed before correction")
            insert_document(connection, approval, chunks)
            self._insert_receipt(connection, receipt)

    def delete_document(
        self, document_id: str, expected_digest: str,
        receipt: DocumentManagementReceipt,
    ) -> None:
        self._validate_receipt(receipt)
        if receipt.target_id != document_id or receipt.previous_content_sha256 != expected_digest:
            raise ValueError("deletion receipt does not match document transition")
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM document_index_documents "
                "WHERE document_id=? AND owner_id=? AND source_sha256=?",
                (document_id, self._owner_id, expected_digest),
            )
            if cursor.rowcount != 1:
                raise ValueError("document changed before deletion")
            self._insert_receipt(connection, receipt)

    def expire_grant(
        self, grant_id: str, receipt: DocumentManagementReceipt,
    ) -> None:
        self._validate_receipt(receipt)
        if receipt.target_id != grant_id:
            raise ValueError("expiry receipt does not match its grant")
        with self._database.transaction() as connection:
            rows = connection.execute(
                "SELECT document_id,source_sha256 FROM document_index_documents "
                "WHERE grant_id=? AND owner_id=? ORDER BY document_id",
                (grant_id, self._owner_id),
            ).fetchall()
            identifiers = tuple(str(row[0]) for row in rows)
            if identifiers != receipt.affected_document_ids:
                raise ValueError("expiry receipt does not match grant documents")
            if _aggregate_state(rows) != receipt.previous_content_sha256:
                raise ValueError("grant changed before expiry")
            cursor = connection.execute(
                "DELETE FROM document_index_grants WHERE grant_id=? AND owner_id=?",
                (grant_id, self._owner_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("document grant changed before expiry")
            self._insert_receipt(connection, receipt)

    def receipts(self) -> tuple[DocumentManagementReceipt, ...]:
        rows = self._database.fetchall(
            "SELECT receipt_id,payload_ciphertext FROM document_management_receipts "
            "WHERE owner_id=? ORDER BY performed_at,receipt_id", (self._owner_id,),
        )
        values = tuple(
            decrypt_contract(
                self._cipher, self._owner_id, "document-management-receipt",
                str(row[0]), row[1], DocumentManagementReceipt,
            )
            for row in rows
        )
        if any(not isinstance(value, DocumentManagementReceipt) for value in values):
            raise TypeError("stored document management receipt has an invalid type")
        return tuple(value for value in values if isinstance(value, DocumentManagementReceipt))

    def receipt_for_request(self, request_id: str) -> DocumentManagementReceipt | None:
        row = self._database.fetchone(
            "SELECT receipt_id,payload_ciphertext FROM document_management_receipts "
            "WHERE owner_id=? AND request_id=?", (self._owner_id, request_id),
        )
        if row is None:
            return None
        value = decrypt_contract(
            self._cipher, self._owner_id, "document-management-receipt",
            str(row[0]), row[1], DocumentManagementReceipt,
        )
        if not isinstance(value, DocumentManagementReceipt):
            raise TypeError("stored document management receipt has an invalid type")
        return value

    def _insert_receipt(self, connection, receipt: DocumentManagementReceipt) -> None:
        token = encrypt_contract(
            self._cipher, self._owner_id, "document-management-receipt",
            receipt.receipt_id, receipt,
        )
        connection.execute(
            "INSERT INTO document_management_receipts "
            "(receipt_id,request_id,owner_id,operation,target_id,performed_at,"
            "payload_ciphertext,created_at) VALUES "
            "(?,?,?,?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
            (
                receipt.receipt_id, receipt.request_id, self._owner_id,
                receipt.operation.value,
                receipt.target_id, receipt.performed_at.isoformat(), token,
            ),
        )

    def _validate_receipt(self, receipt: DocumentManagementReceipt) -> None:
        if receipt.owner_id != self._owner_id or receipt.performed_by != self._owner_id:
            raise PermissionError("document management receipt owner is invalid")


def aggregate_document_state(rows) -> str:
    return _aggregate_state(rows)


def _aggregate_state(rows) -> str:
    material = "".join(f"{row[0]}\0{row[1]}\n" for row in rows)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
