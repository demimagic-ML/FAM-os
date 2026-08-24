"""Encrypted bounded staging for captured sources and reviewed synthetic examples."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from fam_os.expert_factory.dataset_provenance import (
    CapturedDatasetSource,
    SyntheticExampleProposal,
    SyntheticExampleReview,
    TrainingCaptureGrant,
)
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqliteDatasetStagingRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def add_source(
        self, grant: TrainingCaptureGrant, source: CapturedDatasetSource,
        now: datetime,
    ) -> bool:
        if source.grant_id != grant.grant_id or source.proposal_id != grant.proposal_id:
            raise ValueError("captured source does not bind its grant")
        if not grant.permits(
            source.source_kind, source.workspace_scope, source.sensitivity, now,
        ):
            raise PermissionError("capture grant does not permit this source")
        content_bytes = _source_bytes(source)
        try:
            with self._database.transaction() as connection:
                self._require_active_grant(connection, grant, now)
                used = connection.execute(
                    "SELECT COALESCE(sum(content_bytes),0) FROM factory_dataset_sources "
                    "WHERE owner_id=? AND grant_id=?",
                    (self._owner_id, grant.grant_id),
                ).fetchone()[0]
                if int(used) + content_bytes > grant.maximum_source_bytes:
                    raise PermissionError("capture grant source-byte budget is exhausted")
                connection.execute(
                    "INSERT INTO factory_dataset_sources VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        self._owner_id, source.source_id, grant.grant_id,
                        source.proposal_id, source.source_family_id,
                        source.partition.value, content_bytes,
                        self._encrypt("factory-dataset-source", source.source_id, source),
                        source.captured_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def add_example(
        self, grant: TrainingCaptureGrant, example: SyntheticExampleProposal,
        now: datetime,
    ) -> bool:
        content_bytes = len(example.input_text.encode()) + len(example.completion.encode())
        try:
            with self._database.transaction() as connection:
                self._require_active_grant(connection, grant, now)
                source = connection.execute(
                    "SELECT grant_id,source_family_id,partition "
                    "FROM factory_dataset_sources WHERE owner_id=? AND source_id=?",
                    (self._owner_id, example.source_id),
                ).fetchone()
                if source is None or tuple(map(str, source)) != (
                    grant.grant_id, example.source_family_id, example.partition.value,
                ):
                    raise ValueError("synthetic example does not inherit source lineage")
                count = connection.execute(
                    "SELECT count(*) FROM factory_synthetic_examples "
                    "WHERE owner_id=? AND grant_id=?",
                    (self._owner_id, grant.grant_id),
                ).fetchone()[0]
                if int(count) >= grant.maximum_examples:
                    raise PermissionError("capture grant example budget is exhausted")
                connection.execute(
                    "INSERT INTO factory_synthetic_examples VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        self._owner_id, example.example_id, grant.grant_id,
                        example.source_id, example.source_family_id,
                        example.partition.value, content_bytes,
                        self._encrypt(
                            "factory-synthetic-example", example.example_id, example,
                        ),
                        example.generated_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def add_review(self, review: SyntheticExampleReview) -> bool:
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO factory_synthetic_reviews VALUES (?,?,?,?,?,?)",
                    (
                        self._owner_id, review.review_id, review.example_id,
                        int(review.accepted),
                        self._encrypt(
                            "factory-synthetic-review", review.review_id, review,
                        ),
                        review.reviewed_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def sources(self, grant_id: str) -> tuple[CapturedDatasetSource, ...]:
        return self._read_many(
            "factory_dataset_sources", "source_id", "factory-dataset-source",
            CapturedDatasetSource, "captured_at", grant_id,
        )

    def examples(self, grant_id: str) -> tuple[SyntheticExampleProposal, ...]:
        return self._read_many(
            "factory_synthetic_examples", "example_id",
            "factory-synthetic-example", SyntheticExampleProposal,
            "generated_at", grant_id,
        )

    def reviews(self, grant_id: str) -> tuple[SyntheticExampleReview, ...]:
        rows = self._database.fetchall(
            "SELECT r.review_id,r.payload_ciphertext FROM factory_synthetic_reviews r "
            "JOIN factory_synthetic_examples e "
            "ON e.owner_id=r.owner_id AND e.example_id=r.example_id "
            "WHERE r.owner_id=? AND e.grant_id=? "
            "ORDER BY r.reviewed_at,r.review_id",
            (self._owner_id, grant_id),
        )
        return tuple(
            self._decrypt(
                "factory-synthetic-review", row[0], row[1], SyntheticExampleReview,
            )
            for row in rows
        )

    def _read_many(self, table, identity, kind, expected, order, grant_id):
        rows = self._database.fetchall(
            f"SELECT {identity},payload_ciphertext FROM {table} "
            f"WHERE owner_id=? AND grant_id=? ORDER BY {order},{identity}",
            (self._owner_id, grant_id),
        )
        return tuple(self._decrypt(kind, row[0], row[1], expected) for row in rows)

    def _require_active_grant(self, connection, grant, now) -> None:
        row = connection.execute(
            "SELECT proposal_id,revision,active,expires_at,maximum_source_bytes,"
            "maximum_examples FROM factory_capture_grants "
            "WHERE owner_id=? AND grant_id=?",
            (self._owner_id, grant.grant_id),
        ).fetchone()
        expected = (
            grant.proposal_id, grant.revision, 1, grant.expires_at.isoformat(),
            grant.maximum_source_bytes, grant.maximum_examples,
        )
        if row is None or tuple(row) != expected or now >= grant.expires_at:
            raise PermissionError("capture grant is absent, expired, revoked, or changed")

    def _encrypt(self, kind: str, identifier: str, value: object) -> str:
        return encrypt_contract(self._cipher, self._owner_id, kind, identifier, value)

    def _decrypt(self, kind: str, identifier, token, expected):
        if not isinstance(identifier, str) or not isinstance(token, str):
            raise TypeError("stored dataset staging row is invalid")
        value = decrypt_contract(
            self._cipher, self._owner_id, kind, identifier, token, expected,
        )
        if not isinstance(value, expected):
            raise TypeError("stored dataset staging contract is invalid")
        return value


def _source_bytes(source: CapturedDatasetSource) -> int:
    return len(source.input_text.encode()) + len((source.reference_output or "").encode())
