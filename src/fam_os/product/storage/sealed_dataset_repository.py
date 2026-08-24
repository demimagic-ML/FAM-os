"""Encrypted immutable Expert Factory datasets and leakage evidence."""

from __future__ import annotations

import sqlite3

from fam_os.expert_factory import (
    DatasetLeakageReport,
    SealedDatasetBlobReceipt,
    SealedFactoryDataset,
)
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqliteSealedDatasetRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def record(
        self,
        report: DatasetLeakageReport,
        dataset: SealedFactoryDataset | None,
        blobs: tuple[SealedDatasetBlobReceipt, ...] = (),
    ) -> bool:
        if dataset is not None and (
            not report.passed
            or dataset.dataset_id != report.candidate_dataset_id
            or dataset.leakage_report_id != report.report_id
        ):
            raise ValueError("sealed dataset does not bind its passed leakage report")
        if dataset is None and report.passed:
            raise ValueError("a passed leakage report requires a sealed dataset")
        if dataset is None and blobs:
            raise ValueError("failed dataset attempts cannot retain partition blobs")
        if dataset is not None:
            expected = tuple(
                (item.blob_id, item.partition, item.ordered_records_sha256)
                for item in dataset.partitions
            )
            actual = tuple(
                (item.blob_id, item.partition, item.plaintext_sha256)
                for item in blobs
                if item.dataset_id == dataset.dataset_id
            )
            if actual != expected or len(actual) != len(blobs):
                raise ValueError("sealed dataset blobs do not match the manifest")
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO factory_dataset_leakage_reports VALUES (?,?,?,?,?,?,?)",
                    (
                        self._owner_id, report.report_id,
                        report.candidate_dataset_id, int(report.passed),
                        report.report_sha256,
                        self._encrypt(
                            "factory-dataset-leakage-report", report.report_id, report,
                        ),
                        report.evaluated_at.isoformat(),
                    ),
                )
                if dataset is not None:
                    connection.execute(
                        "INSERT INTO factory_sealed_datasets VALUES "
                        "(?,?,?,?,?,?,?,1,1,?,?)",
                        (
                            self._owner_id, dataset.dataset_id, dataset.proposal_id,
                            dataset.grant_id, dataset.capability_id,
                            dataset.manifest_sha256, dataset.leakage_report_id,
                            self._encrypt(
                                "factory-sealed-dataset", dataset.dataset_id, dataset,
                            ),
                            dataset.sealed_at.isoformat(),
                        ),
                    )
                    for blob in blobs:
                        connection.execute(
                            "INSERT INTO factory_sealed_dataset_blobs VALUES "
                            "(?,?,?,?,?,?,?,?,?)",
                            (
                                self._owner_id, blob.blob_id, blob.dataset_id,
                                blob.partition.value, blob.plaintext_sha256,
                                blob.ciphertext_sha256, blob.relative_path,
                                self._encrypt(
                                    "factory-sealed-dataset-blob", blob.blob_id, blob,
                                ),
                                blob.created_at.isoformat(),
                            ),
                        )
        except sqlite3.IntegrityError:
            existing_report = self.report(report.report_id)
            existing_dataset = self.get(report.candidate_dataset_id)
            existing_blobs = self.blobs(report.candidate_dataset_id)
            if (
                existing_report != report or existing_dataset != dataset
                or existing_blobs != blobs
            ):
                raise RuntimeError("sealed dataset attempt identity was reused") from None
            return False
        return True

    def get(self, dataset_id: str) -> SealedFactoryDataset | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM factory_sealed_datasets "
            "WHERE owner_id=? AND dataset_id=?",
            (self._owner_id, dataset_id),
        )
        if row is None:
            return None
        return self._decrypt(
            "factory-sealed-dataset", dataset_id, row[0], SealedFactoryDataset,
        )

    def report(self, report_id: str) -> DatasetLeakageReport | None:
        row = self._database.fetchone(
            "SELECT payload_ciphertext FROM factory_dataset_leakage_reports "
            "WHERE owner_id=? AND report_id=?",
            (self._owner_id, report_id),
        )
        if row is None:
            return None
        return self._decrypt(
            "factory-dataset-leakage-report", report_id, row[0],
            DatasetLeakageReport,
        )

    def datasets(self) -> tuple[SealedFactoryDataset, ...]:
        rows = self._database.fetchall(
            "SELECT dataset_id,payload_ciphertext FROM factory_sealed_datasets "
            "WHERE owner_id=? ORDER BY sealed_at,dataset_id",
            (self._owner_id,),
        )
        return tuple(
            self._decrypt(
                "factory-sealed-dataset", row[0], row[1], SealedFactoryDataset,
            )
            for row in rows
        )

    def reports(self) -> tuple[DatasetLeakageReport, ...]:
        rows = self._database.fetchall(
            "SELECT report_id,payload_ciphertext "
            "FROM factory_dataset_leakage_reports WHERE owner_id=? "
            "ORDER BY recorded_at,report_id",
            (self._owner_id,),
        )
        return tuple(
            self._decrypt(
                "factory-dataset-leakage-report", row[0], row[1],
                DatasetLeakageReport,
            )
            for row in rows
        )

    def blobs(self, dataset_id: str) -> tuple[SealedDatasetBlobReceipt, ...]:
        rows = self._database.fetchall(
            "SELECT blob_id,payload_ciphertext FROM factory_sealed_dataset_blobs "
            "WHERE owner_id=? AND dataset_id=? ORDER BY "
            "CASE partition WHEN 'train' THEN 1 WHEN 'validation' THEN 2 ELSE 3 END",
            (self._owner_id, dataset_id),
        )
        return tuple(
            self._decrypt(
                "factory-sealed-dataset-blob", row[0], row[1],
                SealedDatasetBlobReceipt,
            )
            for row in rows
        )

    def _encrypt(self, kind: str, identifier: str, value: object) -> str:
        return encrypt_contract(self._cipher, self._owner_id, kind, identifier, value)

    def _decrypt(self, kind: str, identifier, token, expected):
        if not isinstance(identifier, str) or not isinstance(token, str):
            raise TypeError("stored sealed dataset row is invalid")
        value = decrypt_contract(
            self._cipher, self._owner_id, kind, identifier, token, expected,
        )
        if not isinstance(value, expected):
            raise TypeError("stored sealed dataset contract is invalid")
        return value
