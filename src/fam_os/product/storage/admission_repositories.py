"""Durable Core admission replay and authority repositories."""

from __future__ import annotations

import sqlite3

from fam_os.core.admission.contracts import RequestAuthorityGrant
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.database import ProductionDatabase


class SqliteRequestReplayRegistry:
    def __init__(self, database: ProductionDatabase) -> None:
        self._database = database

    def reserve(self, request_id: str) -> bool:
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO core_replay(reservation_kind,reservation_id) VALUES (?,?)",
                    ("request", request_id),
                )
        except sqlite3.IntegrityError:
            return False
        return True


class SqliteRequestAuthorityRegistry:
    def __init__(
        self,
        database: ProductionDatabase,
        cipher: ProductPayloadCipher,
        owner_id: str,
    ) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def add(self, grant: RequestAuthorityGrant) -> bool:
        token = encrypt_contract(
            self._cipher, self._owner_id, "authority", grant.authority_ref, grant,
        )
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO authority_grants(authority_ref,payload_ciphertext) VALUES (?,?)",
                    (grant.authority_ref, token),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def get(self, authority_ref: str) -> RequestAuthorityGrant | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM authority_grants WHERE authority_ref=?",
            (authority_ref,),
        )
        if row is None:
            return None
        token = row[0]
        if not isinstance(token, str):
            raise TypeError("stored authority payload is not text")
        value = decrypt_contract(
            self._cipher, self._owner_id, "authority", authority_ref,
            token, RequestAuthorityGrant,
        )
        assert isinstance(value, RequestAuthorityGrant)
        return value
