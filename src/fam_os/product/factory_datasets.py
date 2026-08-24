"""Owner-governed capture and provenance-bound synthetic generation service."""

from __future__ import annotations

from datetime import UTC, datetime

from fam_os.expert_factory import (
    CapturedDatasetSource,
    HeldOutEvaluationKind,
    HeldOutVerifierKind,
    DatasetPartition,
    DatasetLeakageReport,
    DatasetSplitPolicy,
    SyntheticExampleProposal,
    SyntheticExampleReview,
    SealedFactoryDataset,
    TrainingCaptureGrant,
    TrainingDataSensitivity,
    TrainingSourceKind,
    build_captured_source,
    build_synthetic_example,
    canonical_partition_bytes,
    seal_factory_dataset,
)
from fam_os.expert_factory.synthetic_generation import (
    SyntheticExampleReviewer,
    SyntheticTeacher,
)


class ProductFactoryDatasets:
    def __init__(
        self, repositories, split_policy: DatasetSplitPolicy, blob_store=None, now=None,
    ) -> None:
        self._repositories = repositories
        self._split_policy = split_policy
        self._blob_store = blob_store
        self._now = now or (lambda: datetime.now(UTC))

    def add_grant(self, grant: TrainingCaptureGrant) -> bool:
        proposals = self._repositories.factory_discovery.proposals()
        proposal = next(
            (item for item in proposals if item.proposal_id == grant.proposal_id), None,
        )
        if proposal is None or proposal.capability_id != grant.capability_id:
            raise ValueError("capture grant does not bind an existing capability proposal")
        return self._repositories.capture_grants.add(grant)

    def capture_source(
        self, *, grant_id: str, source_id: str, source_family_id: str,
        source_kind: TrainingSourceKind, workspace_scope: str,
        sensitivity: TrainingDataSensitivity, license_id: str, input_text: str,
        reference_output: str | None,
        evaluation_kind: HeldOutEvaluationKind | None = None,
        evaluation_verifier: HeldOutVerifierKind | None = None,
        evaluation_requirement_id: str | None = None,
    ) -> CapturedDatasetSource:
        now = self._now()
        grant = self._require_grant(grant_id, now)
        source = build_captured_source(
            source_id=source_id, grant_id=grant.grant_id,
            proposal_id=grant.proposal_id, source_family_id=source_family_id,
            split_policy=self._split_policy, source_kind=source_kind,
            workspace_scope=workspace_scope, sensitivity=sensitivity,
            license_id=license_id, input_text=input_text,
            reference_output=reference_output, captured_at=now,
            evaluation_kind=evaluation_kind,
            evaluation_verifier=evaluation_verifier,
            evaluation_requirement_id=evaluation_requirement_id,
        )
        if not self._repositories.dataset_staging.add_source(grant, source, now):
            existing = self._source(grant_id, source_id)
            if existing != source:
                raise RuntimeError("dataset source identity was reused")
            return existing
        return source

    def generate(
        self, *, grant_id: str, source_id: str, teacher: SyntheticTeacher,
        reviewer: SyntheticExampleReviewer, maximum_examples: int,
    ) -> tuple[tuple[SyntheticExampleProposal, SyntheticExampleReview], ...]:
        examples = self.generate_proposals(
            grant_id=grant_id, source_id=source_id, teacher=teacher,
            maximum_examples=maximum_examples,
        )
        results = []
        for example in examples:
            review = reviewer.review(example)
            self.review(grant_id=grant_id, review=review)
            results.append((example, review))
        return tuple(results)

    def generate_proposals(
        self, *, grant_id: str, source_id: str, teacher: SyntheticTeacher,
        maximum_examples: int,
    ) -> tuple[SyntheticExampleProposal, ...]:
        now = self._now()
        grant = self._require_grant(grant_id, now)
        if maximum_examples < 1 or maximum_examples > grant.maximum_examples:
            raise ValueError("synthetic generation example bound is invalid")
        source = self._source(grant_id, source_id)
        if source.partition is DatasetPartition.HELD_OUT:
            raise PermissionError("held-out sources are unavailable to teachers")
        generated = teacher.generate(source, maximum_examples)
        if not generated or len(generated) > maximum_examples:
            raise ValueError("teacher returned an invalid number of examples")
        results = []
        for ordinal, content in enumerate(generated, 1):
            generated_at = self._now()
            example = build_synthetic_example(
                source=source, teacher_model_ref=teacher.model_ref,
                teacher_manifest_sha256=teacher.manifest_sha256,
                input_text=content.input_text, completion=content.completion,
                generated_at=generated_at, ordinal=ordinal,
            )
            if not self._repositories.dataset_staging.add_example(
                grant, example, generated_at,
            ):
                raise RuntimeError("synthetic example identity was reused")
            results.append(example)
        return tuple(results)

    def review(
        self, *, grant_id: str, review: SyntheticExampleReview,
    ) -> SyntheticExampleReview:
        self._require_grant(grant_id, self._now())
        example = next(
            (
                item for item in self._repositories.dataset_staging.examples(grant_id)
                if item.example_id == review.example_id
            ),
            None,
        )
        if example is None:
            raise KeyError("synthetic example is unavailable")
        if not self._repositories.dataset_staging.add_review(review):
            raise RuntimeError("synthetic example was already reviewed")
        return review

    def accepted_examples(self, grant_id: str) -> tuple[SyntheticExampleProposal, ...]:
        accepted = {
            item.example_id for item in self._repositories.dataset_staging.reviews(grant_id)
            if item.accepted
        }
        return tuple(
            item for item in self._repositories.dataset_staging.examples(grant_id)
            if item.example_id in accepted
        )

    def seal(
        self, *, dataset_id: str, grant_id: str,
        near_duplicate_threshold_ppm: int = 900_000,
    ) -> tuple[SealedFactoryDataset | None, DatasetLeakageReport]:
        report_id = f"dataset-leakage-report-{dataset_id}"
        existing_report = self._repositories.sealed_datasets.report(report_id)
        if existing_report is not None:
            return self._repositories.sealed_datasets.get(dataset_id), existing_report
        now = self._now()
        grant = self._require_grant(grant_id, now)
        sources = self._repositories.dataset_staging.sources(grant_id)
        examples = self._repositories.dataset_staging.examples(grant_id)
        reviews = self._repositories.dataset_staging.reviews(grant_id)
        dataset, report = seal_factory_dataset(
            dataset_id=dataset_id, proposal_id=grant.proposal_id,
            capability_id=grant.capability_id, sources=sources,
            examples=examples, reviews=reviews, sealed_at=now,
            near_duplicate_threshold_ppm=near_duplicate_threshold_ppm,
        )
        blobs = ()
        if dataset is not None:
            if self._blob_store is None:
                raise RuntimeError("immutable factory dataset blob store is unavailable")
            blobs = tuple(
                self._blob_store.put(
                    blob_id=partition.blob_id, dataset_id=dataset.dataset_id,
                    partition=partition.partition,
                    plaintext_sha256=partition.ordered_records_sha256,
                    payload=canonical_partition_bytes(
                        partition, sources, examples, reviews,
                    ),
                    created_at=now,
                )
                for partition in dataset.partitions
            )
        self._repositories.sealed_datasets.record(report, dataset, blobs)
        return dataset, report

    def _require_grant(self, grant_id: str, now: datetime) -> TrainingCaptureGrant:
        grant = self._repositories.capture_grants.active(grant_id, now)
        if grant is None:
            raise PermissionError("capture grant is absent, expired, or revoked")
        return grant

    def _source(self, grant_id: str, source_id: str) -> CapturedDatasetSource:
        source = next(
            (
                item for item in self._repositories.dataset_staging.sources(grant_id)
                if item.source_id == source_id
            ),
            None,
        )
        if source is None:
            raise KeyError("captured dataset source is unavailable")
        return source
