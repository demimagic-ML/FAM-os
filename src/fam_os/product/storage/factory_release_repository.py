"""Encrypted specialist release, canary, and activation evidence."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import TypeVar

from fam_os.expert_factory import (
    FactoryActivationDecision,
    FactoryCanaryApproval,
    FactoryCanaryReport,
    FactorySpecialistPackageReceipt,
    FactorySpecialistReleaseLineage,
)
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.database import ProductionDatabase


T = TypeVar("T")


class SqliteFactoryReleaseRepository:
    def __init__(
        self, database: ProductionDatabase, cipher: ProductPayloadCipher,
        owner_id: str,
    ) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def record_package(
        self, lineage: FactorySpecialistReleaseLineage,
        receipt: FactorySpecialistPackageReceipt,
    ) -> bool:
        if (
            receipt.release_id != lineage.release_id
            or receipt.package_id != lineage.package_id
            or receipt.package_version != lineage.package_version
            or receipt.lineage_sha256 != lineage.lineage_sha256
        ):
            raise ValueError("specialist package receipt does not match lineage")
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO factory_specialist_release_lineages "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        self._owner_id, lineage.release_id, lineage.package_id,
                        lineage.package_version, lineage.comparison_decision_id,
                        lineage.conversion_receipt_id, lineage.lineage_sha256,
                        self._encrypt(
                            "factory-release-lineage", lineage.release_id, lineage,
                        ), lineage.created_at.isoformat(),
                    ),
                )
                connection.execute(
                    "INSERT INTO factory_specialist_package_receipts "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        self._owner_id, receipt.receipt_id, receipt.release_id,
                        receipt.package_id, receipt.package_version,
                        receipt.receipt_sha256,
                        self._encrypt(
                            "factory-package-receipt", receipt.receipt_id, receipt,
                        ), receipt.installed_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            existing = self.package_receipt(receipt.receipt_id)
            if existing == receipt and self.lineage(lineage.release_id) == lineage:
                return False
            raise RuntimeError("specialist package identity was reused") from None
        return True

    def add_canary_approval(self, value: FactoryCanaryApproval) -> bool:
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO factory_canary_approvals VALUES "
                    "(?,?,?,?,?,1,0,?,?,?,?)",
                    (
                        self._owner_id, value.approval_id,
                        value.package_receipt_sha256, value.one_use_canary_id,
                        value.revision, value.expires_at.isoformat(),
                        self._encrypt(
                            "factory-canary-approval", value.approval_id, value,
                        ), value.issued_at.isoformat(), value.issued_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            existing = self.canary_approval(value.approval_id)
            if existing == value:
                return False
            if existing is not None:
                raise RuntimeError("factory canary approval identity was reused") from None
            raise PermissionError("canary requires a signed installed package") from None
        return True

    def claim_canary(
        self, approval_id: str, canary_id: str, revision: int,
        claimed_at: datetime,
    ) -> None:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE factory_canary_approvals SET consumed=1,updated_at=? "
                "WHERE owner_id=? AND approval_id=? AND one_use_canary_id=? "
                "AND revision=? AND active=1 AND consumed=0 AND expires_at>?",
                (
                    claimed_at.isoformat(), self._owner_id, approval_id,
                    canary_id, revision, claimed_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                raise PermissionError("factory canary approval is unavailable")

    def complete_canary(
        self, report: FactoryCanaryReport,
        decision: FactoryActivationDecision,
    ) -> None:
        approval = self.canary_approval(report.approval_id)
        if approval is None or (
            report.canary_id != approval.one_use_canary_id
            or report.package_receipt_sha256 != approval.package_receipt_sha256
            or decision.approval_id != approval.approval_id
            or decision.canary_id != report.canary_id
            or decision.report_sha256 != report.report_sha256
            or decision.package_receipt_sha256 != approval.package_receipt_sha256
        ):
            raise PermissionError("factory canary evidence does not match approval")
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT consumed FROM factory_canary_approvals "
                "WHERE owner_id=? AND approval_id=?",
                (self._owner_id, approval.approval_id),
            ).fetchone()
            if row is None or row[0] != 1:
                raise PermissionError("factory canary was not claimed")
            connection.execute(
                "INSERT INTO factory_canary_reports VALUES (?,?,?,?,?,?,?,?)",
                (
                    self._owner_id, report.report_id, report.approval_id,
                    report.canary_id, report.status.value, report.report_sha256,
                    self._encrypt(
                        "factory-canary-report", report.report_id, report,
                    ), report.finished_at.isoformat(),
                ),
            )
            connection.execute(
                "INSERT INTO factory_activation_decisions VALUES "
                "(?,?,?,?,?,?,?,?,?)",
                (
                    self._owner_id, decision.decision_id,
                    decision.approval_id, decision.canary_id,
                    decision.report_sha256, int(decision.activate),
                    decision.decision_sha256,
                    self._encrypt(
                        "factory-activation-decision", decision.decision_id,
                        decision,
                    ), decision.decided_at.isoformat(),
                ),
            )

    def lineage(self, release_id: str) -> FactorySpecialistReleaseLineage | None:
        return self._one(
            "factory_specialist_release_lineages", "release_id", release_id,
            "factory-release-lineage", FactorySpecialistReleaseLineage,
        )

    def package_receipt(
        self, receipt_id: str,
    ) -> FactorySpecialistPackageReceipt | None:
        return self._one(
            "factory_specialist_package_receipts", "receipt_id", receipt_id,
            "factory-package-receipt", FactorySpecialistPackageReceipt,
        )

    def package_receipt_by_sha(
        self, receipt_sha256: str,
    ) -> FactorySpecialistPackageReceipt | None:
        return self._one(
            "factory_specialist_package_receipts", "receipt_sha256",
            receipt_sha256, "factory-package-receipt",
            FactorySpecialistPackageReceipt, id_column="receipt_id",
        )

    def canary_approval(self, approval_id: str) -> FactoryCanaryApproval | None:
        return self._one(
            "factory_canary_approvals", "approval_id", approval_id,
            "factory-canary-approval", FactoryCanaryApproval,
        )

    def canary_report(self, canary_id: str) -> FactoryCanaryReport | None:
        return self._one(
            "factory_canary_reports", "canary_id", canary_id,
            "factory-canary-report", FactoryCanaryReport, id_column="report_id",
        )

    def activation_decision(
        self, canary_id: str,
    ) -> FactoryActivationDecision | None:
        return self._one(
            "factory_activation_decisions", "canary_id", canary_id,
            "factory-activation-decision", FactoryActivationDecision,
            id_column="decision_id",
        )

    def lineages(self) -> tuple[FactorySpecialistReleaseLineage, ...]:
        return self._all(
            "factory_specialist_release_lineages", "release_id", "created_at",
            "factory-release-lineage", FactorySpecialistReleaseLineage,
        )

    def package_receipts(self) -> tuple[FactorySpecialistPackageReceipt, ...]:
        return self._all(
            "factory_specialist_package_receipts", "receipt_id", "installed_at",
            "factory-package-receipt", FactorySpecialistPackageReceipt,
        )

    def canary_approvals(self) -> tuple[FactoryCanaryApproval, ...]:
        return self._all(
            "factory_canary_approvals", "approval_id", "created_at",
            "factory-canary-approval", FactoryCanaryApproval,
        )

    def canary_reports(self) -> tuple[FactoryCanaryReport, ...]:
        return self._all(
            "factory_canary_reports", "report_id", "finished_at",
            "factory-canary-report", FactoryCanaryReport,
        )

    def activation_decisions(self) -> tuple[FactoryActivationDecision, ...]:
        return self._all(
            "factory_activation_decisions", "decision_id", "decided_at",
            "factory-activation-decision", FactoryActivationDecision,
        )

    def _one(
        self, table: str, column: str, value: str, kind: str,
        expected: type[T], *, id_column: str | None = None,
    ) -> T | None:
        identifier = id_column or column
        row = self._database.fetchone(
            f"SELECT {identifier},payload_ciphertext FROM {table} "
            f"WHERE owner_id=? AND {column}=?", (self._owner_id, value),
        )
        if row is None:
            return None
        return self._decrypt(kind, row[0], row[1], expected)

    def _all(
        self, table: str, identifier: str, order: str, kind: str,
        expected: type[T],
    ) -> tuple[T, ...]:
        rows = self._database.fetchall(
            f"SELECT {identifier},payload_ciphertext FROM {table} "
            f"WHERE owner_id=? ORDER BY {order},{identifier}",
            (self._owner_id,),
        )
        return tuple(
            self._decrypt(kind, row[0], row[1], expected) for row in rows
        )

    def _encrypt(self, kind: str, identifier: str, value: object) -> str:
        return encrypt_contract(self._cipher, self._owner_id, kind, identifier, value)

    def _decrypt(
        self, kind: str, identifier: object, token: object, expected: type[T],
    ) -> T:
        if not isinstance(identifier, str) or not isinstance(token, str):
            raise TypeError("stored factory release row is invalid")
        result = decrypt_contract(
            self._cipher, self._owner_id, kind, identifier, token, expected,
        )
        if not isinstance(result, expected):
            raise TypeError("stored factory release contract is invalid")
        return result
