"""Immutable dataset manifests with exact/near deduplication and leakage gates."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from fam_os.expert_factory.dataset_provenance import (
    CapturedDatasetSource,
    DatasetPartition,
    SyntheticExampleProposal,
    SyntheticExampleReview,
)


FACTORY_SEALED_DATASET_VERSION = "fam.factory.sealed-dataset/v1alpha1"
_TOKEN = re.compile(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]")


class DatasetLeakageKind(StrEnum):
    SOURCE_FAMILY_CROSSED_PARTITIONS = "source_family_crossed_partitions"
    EXACT_CROSS_PARTITION = "exact_cross_partition"
    NEAR_CROSS_PARTITION = "near_cross_partition"


@dataclass(frozen=True, slots=True)
class SealedDatasetPartition:
    partition: DatasetPartition
    blob_id: str
    record_ids: tuple[str, ...]
    record_count: int
    content_bytes: int
    ordered_records_sha256: str
    contract_version: str = FACTORY_SEALED_DATASET_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.partition, DatasetPartition):
            raise ValueError("sealed dataset partition is invalid")
        if not self.blob_id.strip():
            raise ValueError("sealed dataset partition blob identity is invalid")
        if not self.record_ids or self.record_ids != tuple(sorted(set(self.record_ids))):
            raise ValueError("sealed partition record IDs must be sorted and unique")
        if self.record_count != len(self.record_ids) or self.content_bytes < 1:
            raise ValueError("sealed partition counts are invalid")
        _sha256(self.ordered_records_sha256, "ordered_records_sha256")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class DatasetLeakageFinding:
    finding_id: str
    kind: DatasetLeakageKind
    left_record_id: str
    right_record_id: str
    similarity_ppm: int
    blocking: bool = True
    contract_version: str = FACTORY_SEALED_DATASET_VERSION

    def __post_init__(self) -> None:
        for value in (self.finding_id, self.left_record_id, self.right_record_id):
            if not value.strip():
                raise ValueError("dataset leakage finding identity is invalid")
        if not isinstance(self.kind, DatasetLeakageKind):
            raise ValueError("dataset leakage kind is invalid")
        if not 0 <= self.similarity_ppm <= 1_000_000:
            raise ValueError("dataset leakage similarity is invalid")
        if not self.blocking:
            raise ValueError("cross-partition leakage findings must block sealing")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class DatasetLeakageReport:
    report_id: str
    candidate_dataset_id: str
    input_record_count: int
    retained_record_count: int
    exact_duplicates_removed: tuple[str, ...]
    near_duplicates_removed: tuple[str, ...]
    near_duplicate_threshold_ppm: int
    findings: tuple[DatasetLeakageFinding, ...]
    evaluated_at: datetime
    passed: bool
    report_sha256: str
    contract_version: str = FACTORY_SEALED_DATASET_VERSION

    def __post_init__(self) -> None:
        if not self.report_id.strip() or not self.candidate_dataset_id.strip():
            raise ValueError("dataset leakage report identity is invalid")
        if self.input_record_count < 1 or not 1 <= self.retained_record_count <= self.input_record_count:
            raise ValueError("dataset leakage report counts are invalid")
        removed = (*self.exact_duplicates_removed, *self.near_duplicates_removed)
        if len(set(removed)) != len(removed):
            raise ValueError("dataset deduplication removal identities must be unique")
        if not 500_000 <= self.near_duplicate_threshold_ppm <= 1_000_000:
            raise ValueError("near-duplicate threshold is invalid")
        if self.passed == bool(self.findings):
            raise ValueError("dataset leakage pass state is inconsistent")
        _aware(self.evaluated_at)
        _sha256(self.report_sha256, "report_sha256")
        if self.report_sha256 != leakage_report_digest(self):
            raise ValueError("dataset leakage report digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class SealedFactoryDataset:
    dataset_id: str
    proposal_id: str
    grant_id: str
    capability_id: str
    split_policy_id: str
    partitions: tuple[SealedDatasetPartition, ...]
    source_ids: tuple[str, ...]
    synthetic_example_ids: tuple[str, ...]
    license_ids: tuple[str, ...]
    sensitivities: tuple[str, ...]
    leakage_report_id: str
    sealed_at: datetime
    manifest_sha256: str
    immutable: bool = True
    training_ready: bool = True
    contract_version: str = FACTORY_SEALED_DATASET_VERSION

    def __post_init__(self) -> None:
        for value in (
            self.dataset_id, self.proposal_id, self.grant_id, self.capability_id,
            self.split_policy_id, self.leakage_report_id,
        ):
            if not value.strip():
                raise ValueError("sealed dataset identity is invalid")
        if tuple(item.partition for item in self.partitions) != tuple(DatasetPartition):
            raise ValueError("sealed dataset must contain ordered train, validation, held-out")
        for values in (
            self.source_ids, self.license_ids, self.sensitivities,
        ):
            if not values or values != tuple(sorted(set(values))):
                raise ValueError("sealed dataset manifest values must be sorted and unique")
        if self.synthetic_example_ids != tuple(sorted(set(self.synthetic_example_ids))):
            raise ValueError("sealed synthetic example IDs must be sorted and unique")
        _aware(self.sealed_at)
        _sha256(self.manifest_sha256, "manifest_sha256")
        if not self.immutable or not self.training_ready:
            raise ValueError("sealed dataset must be immutable and training ready")
        if self.manifest_sha256 != sealed_dataset_digest(self):
            raise ValueError("sealed dataset manifest digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class SealedDatasetBlobReceipt:
    blob_id: str
    dataset_id: str
    partition: DatasetPartition
    plaintext_sha256: str
    ciphertext_sha256: str
    plaintext_bytes: int
    ciphertext_bytes: int
    relative_path: str
    created_at: datetime
    receipt_sha256: str
    contract_version: str = FACTORY_SEALED_DATASET_VERSION

    def __post_init__(self) -> None:
        if not self.blob_id.strip() or not self.dataset_id.strip():
            raise ValueError("sealed dataset blob identity is invalid")
        if not isinstance(self.partition, DatasetPartition):
            raise ValueError("sealed dataset blob partition is invalid")
        _sha256(self.plaintext_sha256, "plaintext_sha256")
        _sha256(self.ciphertext_sha256, "ciphertext_sha256")
        if self.plaintext_bytes < 1 or self.ciphertext_bytes < self.plaintext_bytes:
            raise ValueError("sealed dataset blob sizes are invalid")
        if (
            not self.relative_path.startswith("blobs/")
            or self.relative_path.startswith("/")
            or ".." in self.relative_path.split("/")
        ):
            raise ValueError("sealed dataset blob path is invalid")
        _aware(self.created_at)
        _sha256(self.receipt_sha256, "receipt_sha256")
        if self.receipt_sha256 != sealed_dataset_blob_digest(self):
            raise ValueError("sealed dataset blob receipt digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class _Record:
    record_id: str
    source_id: str
    source_family_id: str
    partition: DatasetPartition
    input_text: str
    completion: str
    license_id: str
    sensitivity: str
    synthetic: bool
    evaluation_kind: str | None
    evaluation_verifier: str | None
    evaluation_requirement_id: str | None

    @property
    def normalized(self) -> str:
        return " ".join(_TOKEN.findall(f"{self.input_text}\n{self.completion}".casefold()))

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(self.normalized.encode()).hexdigest()

    @property
    def content_bytes(self) -> int:
        return len(self.input_text.encode()) + len(self.completion.encode())


def seal_factory_dataset(
    *, dataset_id: str, proposal_id: str, capability_id: str,
    sources: tuple[CapturedDatasetSource, ...],
    examples: tuple[SyntheticExampleProposal, ...],
    reviews: tuple[SyntheticExampleReview, ...], sealed_at: datetime,
    near_duplicate_threshold_ppm: int = 900_000,
) -> tuple[SealedFactoryDataset | None, DatasetLeakageReport]:
    records = _records(sources, examples, reviews)
    if not records:
        raise ValueError("dataset sealing requires accepted records")
    if {item.proposal_id for item in sources} != {proposal_id}:
        raise ValueError("sealed sources must bind the selected capability proposal")
    grant_ids = {item.grant_id for item in sources}
    if len(grant_ids) != 1:
        raise ValueError("sealed sources must use one capture grant")
    retained, exact_removed = _exact_deduplicate(records)
    retained, near_removed, findings = _near_deduplicate(
        retained, near_duplicate_threshold_ppm,
    )
    findings = (*_family_findings(retained), *findings)
    report = _report(
        dataset_id, len(records), len(retained), exact_removed, near_removed,
        near_duplicate_threshold_ppm,
        tuple(sorted(findings, key=lambda item: item.finding_id)), sealed_at,
    )
    if not report.passed:
        return None, report
    partitions = tuple(
        _partition(dataset_id, partition, retained) for partition in DatasetPartition
    )
    source_ids = tuple(sorted({item.source_id for item in retained}))
    synthetic_ids = tuple(sorted(item.record_id for item in retained if item.synthetic))
    licenses = tuple(sorted({item.license_id for item in retained}))
    sensitivities = tuple(sorted({item.sensitivity for item in retained}))
    split_policy_ids = {item.split_policy_id for item in sources}
    if len(split_policy_ids) != 1:
        raise ValueError("sealed sources must use one split policy")
    grant_id = next(iter(grant_ids))
    split_policy_id = next(iter(split_policy_ids))
    values = {
        "dataset_id": dataset_id,
        "proposal_id": proposal_id,
        "grant_id": grant_id,
        "capability_id": capability_id,
        "split_policy_id": split_policy_id,
        "partitions": partitions,
        "source_ids": source_ids,
        "synthetic_example_ids": synthetic_ids,
        "license_ids": licenses,
        "sensitivities": sensitivities,
        "leakage_report_id": report.report_id,
        "sealed_at": sealed_at,
    }
    manifest_sha256 = _sealed_values_digest(values)
    return SealedFactoryDataset(
        dataset_id, proposal_id, grant_id, capability_id, split_policy_id,
        partitions, source_ids, synthetic_ids, licenses, sensitivities,
        report.report_id, sealed_at, manifest_sha256,
    ), report


def _records(
    sources: tuple[CapturedDatasetSource, ...],
    examples: tuple[SyntheticExampleProposal, ...],
    reviews: tuple[SyntheticExampleReview, ...],
) -> tuple[_Record, ...]:
    source_map = {item.source_id: item for item in sources}
    accepted = {item.example_id for item in reviews if item.accepted}
    records = [
        _Record(
            item.source_id, item.source_id, item.source_family_id, item.partition,
            item.input_text, item.reference_output, item.license_id,
            item.sensitivity.value, False,
            None if item.evaluation_kind is None else item.evaluation_kind.value,
            None if item.evaluation_verifier is None else item.evaluation_verifier.value,
            item.evaluation_requirement_id,
        )
        for item in sources if item.reference_output is not None
    ]
    for example in examples:
        if example.example_id not in accepted:
            continue
        source = source_map.get(example.source_id)
        if source is None or (
            source.source_family_id != example.source_family_id
            or source.partition is not example.partition
        ):
            raise ValueError("accepted synthetic example has broken source lineage")
        records.append(_Record(
            example.example_id, source.source_id, source.source_family_id,
            example.partition, example.input_text, example.completion,
            source.license_id, source.sensitivity.value, True,
            None if source.evaluation_kind is None else source.evaluation_kind.value,
            None if source.evaluation_verifier is None else source.evaluation_verifier.value,
            source.evaluation_requirement_id,
        ))
    return tuple(records)


def _exact_deduplicate(
    records: tuple[_Record, ...],
) -> tuple[tuple[_Record, ...], tuple[str, ...]]:
    retained: list[_Record] = []
    removed: list[str] = []
    seen: dict[str, _Record] = {}
    for record in sorted(records, key=lambda item: item.record_id):
        previous = seen.get(record.content_sha256)
        if previous is None:
            seen[record.content_sha256] = record
            retained.append(record)
        elif previous.partition is record.partition:
            removed.append(record.record_id)
        else:
            retained.append(record)
    return tuple(retained), tuple(removed)


def _near_deduplicate(
    records: tuple[_Record, ...], threshold_ppm: int,
) -> tuple[tuple[_Record, ...], tuple[str, ...], tuple[DatasetLeakageFinding, ...]]:
    signatures = {item.record_id: _signature(item.normalized) for item in records}
    buckets: dict[tuple[int, tuple[int, ...]], list[_Record]] = {}
    candidates: set[tuple[str, str]] = set()
    by_id = {item.record_id: item for item in records}
    for record in sorted(records, key=lambda item: item.record_id):
        signature = signatures[record.record_id]
        for band in range(8):
            key = (band, signature[band * 4:(band + 1) * 4])
            for previous in buckets.setdefault(key, []):
                candidates.add((
                    min(previous.record_id, record.record_id),
                    max(previous.record_id, record.record_id),
                ))
            buckets[key].append(record)
    removed: set[str] = set()
    findings: list[DatasetLeakageFinding] = []
    for left_id, right_id in sorted(candidates):
        if left_id in removed or right_id in removed:
            continue
        left, right = by_id[left_id], by_id[right_id]
        similarity = round(_jaccard(left.normalized, right.normalized) * 1_000_000)
        if similarity < threshold_ppm or similarity == 1_000_000:
            continue
        if left.partition is right.partition:
            removed.add(right_id)
        else:
            findings.append(_finding(
                DatasetLeakageKind.NEAR_CROSS_PARTITION, left, right, similarity,
            ))
    return (
        tuple(item for item in records if item.record_id not in removed),
        tuple(sorted(removed)), tuple(findings),
    )


def _family_findings(
    records: tuple[_Record, ...],
) -> tuple[DatasetLeakageFinding, ...]:
    grouped: dict[str, list[_Record]] = {}
    for record in records:
        grouped.setdefault(record.source_family_id, []).append(record)
    findings: list[DatasetLeakageFinding] = []
    for values in grouped.values():
        partitions = {item.partition for item in values}
        if len(partitions) > 1:
            ordered = sorted(values, key=lambda item: item.record_id)
            findings.append(_finding(
                DatasetLeakageKind.SOURCE_FAMILY_CROSSED_PARTITIONS,
                ordered[0], ordered[-1], 1_000_000,
            ))
    hashes: dict[str, list[_Record]] = {}
    for record in records:
        hashes.setdefault(record.content_sha256, []).append(record)
    for values in hashes.values():
        if len({item.partition for item in values}) > 1:
            ordered = sorted(values, key=lambda item: item.record_id)
            findings.append(_finding(
                DatasetLeakageKind.EXACT_CROSS_PARTITION,
                ordered[0], ordered[-1], 1_000_000,
            ))
    return tuple(findings)


def _finding(
    kind: DatasetLeakageKind, left: _Record, right: _Record, similarity: int,
) -> DatasetLeakageFinding:
    digest = hashlib.sha256(
        f"{kind.value}\0{left.record_id}\0{right.record_id}".encode(),
    ).hexdigest()
    return DatasetLeakageFinding(
        f"dataset-leakage-{digest}", kind, left.record_id, right.record_id,
        similarity,
    )


def _partition(
    dataset_id: str, partition: DatasetPartition, records: tuple[_Record, ...],
) -> SealedDatasetPartition:
    values = tuple(sorted(
        (item for item in records if item.partition is partition),
        key=lambda item: item.record_id,
    ))
    if not values:
        raise ValueError(f"sealed dataset has no {partition.value} records")
    ids = tuple(item.record_id for item in values)
    digest = hashlib.sha256(_canonical_records(values)).hexdigest()
    blob_id = "factory-dataset-blob-" + hashlib.sha256(
        f"{dataset_id}\0{partition.value}\0{digest}".encode(),
    ).hexdigest()
    return SealedDatasetPartition(
        partition, blob_id, ids, len(ids),
        sum(item.content_bytes for item in values), digest,
    )


def canonical_partition_bytes(
    partition: SealedDatasetPartition,
    sources: tuple[CapturedDatasetSource, ...],
    examples: tuple[SyntheticExampleProposal, ...],
    reviews: tuple[SyntheticExampleReview, ...],
) -> bytes:
    by_id = {item.record_id: item for item in _records(sources, examples, reviews)}
    try:
        records = tuple(by_id[record_id] for record_id in partition.record_ids)
    except KeyError as error:
        raise ValueError("sealed partition record is unavailable") from error
    payload = _canonical_records(records)
    if hashlib.sha256(payload).hexdigest() != partition.ordered_records_sha256:
        raise ValueError("sealed partition content no longer matches its manifest")
    return payload


def _canonical_records(records: tuple[_Record, ...]) -> bytes:
    lines = (
        json.dumps(
            _record_document(item), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False,
        )
        for item in records
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _record_document(item: _Record) -> dict[str, object]:
    value: dict[str, object] = {
        "completion": item.completion,
        "input": item.input_text,
        "license_id": item.license_id,
        "partition": item.partition.value,
        "record_id": item.record_id,
        "sensitivity": item.sensitivity,
        "source_family_id": item.source_family_id,
        "source_id": item.source_id,
        "synthetic": item.synthetic,
    }
    if item.evaluation_kind is not None:
        value.update({
            "evaluation_kind": item.evaluation_kind,
            "evaluation_requirement_id": item.evaluation_requirement_id,
            "evaluation_verifier": item.evaluation_verifier,
        })
    return value


def _signature(text: str) -> tuple[int, ...]:
    shingles = _shingles(text)
    return tuple(min(
        int.from_bytes(hashlib.sha256(f"{seed}\0{value}".encode()).digest()[:8], "big")
        for value in shingles
    ) for seed in range(32))


def _shingles(text: str) -> frozenset[str]:
    tokens = text.split()
    if len(tokens) < 3:
        return frozenset((text,))
    return frozenset(" ".join(tokens[index:index + 3]) for index in range(len(tokens) - 2))


def _jaccard(left: str, right: str) -> float:
    left_values, right_values = _shingles(left), _shingles(right)
    return len(left_values & right_values) / len(left_values | right_values)


def _report(
    dataset_id: str, input_count: int, retained_count: int,
    exact: tuple[str, ...], near: tuple[str, ...], threshold: int,
    findings: tuple[DatasetLeakageFinding, ...],
    evaluated_at: datetime,
) -> DatasetLeakageReport:
    report_id = f"dataset-leakage-report-{dataset_id}"
    values = {
        "candidate_dataset_id": dataset_id,
        "exact_duplicates_removed": exact,
        "findings": findings,
        "input_record_count": input_count,
        "near_duplicate_threshold_ppm": threshold,
        "near_duplicates_removed": near,
        "retained_record_count": retained_count,
        "report_id": report_id,
        "evaluated_at": evaluated_at,
    }
    digest = _leakage_values_digest(values)
    return DatasetLeakageReport(
        report_id, dataset_id, input_count, retained_count, exact, near,
        threshold, findings, evaluated_at, not findings, digest,
    )


def leakage_report_digest(report: DatasetLeakageReport) -> str:
    return _leakage_values_digest({
        "candidate_dataset_id": report.candidate_dataset_id,
        "exact_duplicates_removed": report.exact_duplicates_removed,
        "findings": report.findings,
        "input_record_count": report.input_record_count,
        "near_duplicate_threshold_ppm": report.near_duplicate_threshold_ppm,
        "near_duplicates_removed": report.near_duplicates_removed,
        "retained_record_count": report.retained_record_count,
        "report_id": report.report_id,
        "evaluated_at": report.evaluated_at,
    })


def _leakage_values_digest(values: dict[str, Any]) -> str:
    findings = [
        {
            "blocking": item.blocking, "finding_id": item.finding_id,
            "kind": item.kind.value, "left": item.left_record_id,
            "right": item.right_record_id, "similarity_ppm": item.similarity_ppm,
        }
        for item in values["findings"]
    ]
    return _json_digest({
        **values, "evaluated_at": values["evaluated_at"].isoformat(),
        "findings": findings,
    })


def sealed_dataset_digest(dataset: SealedFactoryDataset) -> str:
    return _sealed_values_digest({
        "dataset_id": dataset.dataset_id, "proposal_id": dataset.proposal_id,
        "grant_id": dataset.grant_id,
        "capability_id": dataset.capability_id,
        "split_policy_id": dataset.split_policy_id,
        "partitions": dataset.partitions, "source_ids": dataset.source_ids,
        "synthetic_example_ids": dataset.synthetic_example_ids,
        "license_ids": dataset.license_ids, "sensitivities": dataset.sensitivities,
        "leakage_report_id": dataset.leakage_report_id,
        "sealed_at": dataset.sealed_at,
    })


def sealed_dataset_blob_digest(receipt: SealedDatasetBlobReceipt) -> str:
    return _sealed_dataset_blob_values_digest({
        "blob_id": receipt.blob_id,
        "ciphertext_bytes": receipt.ciphertext_bytes,
        "ciphertext_sha256": receipt.ciphertext_sha256,
        "created_at": receipt.created_at,
        "dataset_id": receipt.dataset_id,
        "partition": receipt.partition,
        "plaintext_bytes": receipt.plaintext_bytes,
        "plaintext_sha256": receipt.plaintext_sha256,
        "relative_path": receipt.relative_path,
    })


def build_sealed_dataset_blob_receipt(
    *, blob_id: str, dataset_id: str, partition: DatasetPartition,
    plaintext_sha256: str, ciphertext_sha256: str, plaintext_bytes: int,
    ciphertext_bytes: int, relative_path: str, created_at: datetime,
) -> SealedDatasetBlobReceipt:
    values = {
        "blob_id": blob_id, "dataset_id": dataset_id, "partition": partition,
        "plaintext_sha256": plaintext_sha256,
        "ciphertext_sha256": ciphertext_sha256,
        "plaintext_bytes": plaintext_bytes, "ciphertext_bytes": ciphertext_bytes,
        "relative_path": relative_path, "created_at": created_at,
    }
    return SealedDatasetBlobReceipt(
        blob_id, dataset_id, partition, plaintext_sha256, ciphertext_sha256,
        plaintext_bytes, ciphertext_bytes, relative_path, created_at,
        _sealed_dataset_blob_values_digest(values),
    )


def _sealed_dataset_blob_values_digest(values: dict[str, Any]) -> str:
    return _json_digest({
        **values,
        "partition": values["partition"].value,
        "created_at": values["created_at"].isoformat(),
    })


def _sealed_values_digest(values: dict[str, Any]) -> str:
    partitions = [
        {
            "blob_id": item.blob_id, "content_bytes": item.content_bytes,
            "ordered_records_sha256": item.ordered_records_sha256,
            "partition": item.partition.value, "record_count": item.record_count,
            "record_ids": item.record_ids,
        }
        for item in values["partitions"]
    ]
    return _json_digest({
        **values, "partitions": partitions,
        "sealed_at": values["sealed_at"].isoformat(),
    })


def _json_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()


def _sha256(value: str, name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be lowercase SHA-256")


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("dataset seal time must be timezone-aware")


def _version(value: str) -> None:
    if value != FACTORY_SEALED_DATASET_VERSION:
        raise ValueError("unsupported sealed dataset version")
