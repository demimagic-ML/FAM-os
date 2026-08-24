"""Owner-facing Expert Factory discovery and dataset control facade."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from fam_os.expert_factory import (
    ExampleReviewKind,
    ExpertComparisonDecision,
    FactoryCanaryReport,
    SyntheticExampleReview,
    TrainingCaptureGrant,
    TrainingDataSensitivity,
    TrainingSourceKind,
)
from fam_os.product.factory_teacher import OllamaSyntheticTeacher


class ProductFactoryControl:
    def __init__(
        self, discovery, datasets, repositories, catalog, runtime, model_loader,
        training_approvals=None, training=None, evaluation_approvals=None,
        evaluator=None, release_services=None, now=None,
    ) -> None:
        self._discovery = discovery
        self._datasets = datasets
        self._repositories = repositories
        self._catalog = catalog
        self._runtime = runtime
        self._model_loader = model_loader
        self._training_approvals = training_approvals
        self._training = training
        self._evaluation_approvals = evaluation_approvals
        self._evaluator = evaluator
        self._release = release_services
        self._now = now or (lambda: datetime.now(UTC))

    def traces(self):
        return self._discovery.traces()

    def clusters(self):
        return self._discovery.clusters()

    def proposals(self):
        return self._discovery.proposals()

    def sealed_datasets(self):
        return self._repositories.sealed_datasets.datasets()

    def leakage_reports(self):
        return self._repositories.sealed_datasets.reports()

    def training_approvals(self):
        return () if self._training_approvals is None else (
            self._training_approvals.approvals()
        )

    def training_environments(self):
        return self._repositories.training_jobs.environments()

    def training_jobs(self):
        return self._repositories.training_jobs.jobs()

    def training_terminals(self):
        return self._repositories.training_jobs.terminals()

    def training_admissions(self):
        return self._repositories.training_admissions.decisions()

    def evaluation_approvals(self):
        return () if self._evaluation_approvals is None else (
            self._evaluation_approvals.approvals()
        )

    def held_out_access_receipts(self):
        return tuple(
            receipt for approval in self.evaluation_approvals()
            if (receipt := self._repositories.factory_evaluations.access_receipt(
                approval.one_use_evaluation_id,
            )) is not None
        )

    def evaluation_reports(self):
        return tuple(
            report for approval in self.evaluation_approvals()
            if (report := self._repositories.factory_evaluations.report(
                approval.one_use_evaluation_id,
            )) is not None
        )

    def evaluation_decisions(self) -> tuple[ExpertComparisonDecision, ...]:
        return self._repositories.factory_evaluations.decisions()

    def conversion_approvals(self):
        return self._repositories.factory_conversions.approvals()

    def conversion_environments(self):
        return self._repositories.factory_conversions.environments()

    def conversion_receipts(self):
        return self._repositories.factory_conversions.receipts()

    def release_lineages(self):
        return self._repositories.factory_releases.lineages()

    def package_receipts(self):
        return self._repositories.factory_releases.package_receipts()

    def canary_approvals(self):
        return self._repositories.factory_releases.canary_approvals()

    def canary_reports(self) -> tuple[FactoryCanaryReport, ...]:
        return self._repositories.factory_releases.canary_reports()

    def activation_decisions(self):
        return self._repositories.factory_releases.activation_decisions()

    def specialist_lifecycle_receipts(self):
        return self._repositories.factory_lifecycle.receipts()

    def probe_conversion_environment(self, *, confirmed: bool):
        if not confirmed:
            raise PermissionError("conversion environment probe requires confirmation")
        if self._release is None:
            raise RuntimeError("real release backend is not configured")
        return self._release.conversions.probe_environment()

    def issue_conversion_approval(self, **values):
        if self._release is None:
            raise RuntimeError("real release backend is not configured")
        return self._release.conversions.issue(**values)

    def start_conversion(self, *, approval_id: str, confirmed: bool):
        if self._release is None:
            raise RuntimeError("real release backend is not configured")
        return self._release.conversions.run(
            approval_id=approval_id, confirmed=confirmed,
        )

    def package_specialist(self, **values):
        if self._release is None:
            raise RuntimeError("real release backend is not configured")
        return self._release.releases.package(**values)

    def issue_canary_approval(self, **values):
        if self._release is None:
            raise RuntimeError("real release backend is not configured")
        return self._release.canary_approvals.issue(**values)

    def start_canary(self, *, approval_id: str, confirmed: bool):
        if self._release is None:
            raise RuntimeError("real release backend is not configured")
        return self._release.canary_runner.run(
            approval_id=approval_id, confirmed=confirmed,
        )

    def activate_specialist(self, *, canary_id: str, confirmed: bool):
        if self._release is None:
            raise RuntimeError("real release backend is not configured")
        return self._release.activation.activate(
            canary_id=canary_id, confirmed=confirmed,
        )

    def rollback_specialist(self, **values):
        if self._release is None:
            raise RuntimeError("real release backend is not configured")
        return self._release.lifecycle.manual_rollback(**values)

    def retire_specialist(self, **values):
        if self._release is None:
            raise RuntimeError("real release backend is not configured")
        return self._release.lifecycle.retire(**values)

    def probe_evaluation_environment(self, *, confirmed: bool):
        if not confirmed:
            raise PermissionError("evaluation environment probe requires confirmation")
        if self._evaluator is None:
            raise RuntimeError("real evaluation backend is not configured")
        return self._evaluator.probe()

    def issue_evaluation_approval(self, **values):
        if self._evaluation_approvals is None:
            raise RuntimeError("evaluation approval service is unavailable")
        return self._evaluation_approvals.issue(**values)

    def start_evaluation(self, *, approval_id: str, confirmed: bool):
        if self._evaluator is None:
            raise RuntimeError("real evaluation backend is not configured")
        return self._evaluator.run(approval_id=approval_id, confirmed=confirmed)

    def probe_training_environment(self, *, confirmed: bool):
        if not confirmed:
            raise PermissionError("training environment probe requires confirmation")
        if self._training is None:
            raise RuntimeError("real training backend is not configured")
        return self._training.probe_environment()

    def start_training(
        self, *, request_id: str, approval_id: str, confirmed: bool,
    ):
        if self._training is None:
            raise RuntimeError("real training backend is not configured")
        del request_id
        return self._training.submit(
            approval_id=approval_id, confirmed=confirmed,
        )

    def create_capture_grant(
        self, *, request_id: str, proposal_id: str, capability_id: str,
        source_kinds: tuple[TrainingSourceKind, ...], workspace_scopes: tuple[str, ...],
        sensitivities: tuple[TrainingDataSensitivity, ...], maximum_source_bytes: int,
        maximum_examples: int, lifetime_seconds: int, confirmed: bool,
    ) -> TrainingCaptureGrant:
        if not confirmed:
            raise PermissionError("capture grant requires confirmation")
        if lifetime_seconds < 60 or lifetime_seconds > 30 * 24 * 60 * 60:
            raise ValueError("capture grant lifetime must be 60 seconds to 30 days")
        now = self._now()
        grant = TrainingCaptureGrant(
            f"factory-capture-{request_id}", proposal_id, capability_id,
            source_kinds, workspace_scopes, sensitivities, maximum_source_bytes,
            maximum_examples, now, now + timedelta(seconds=lifetime_seconds), True,
        )
        if not self._datasets.add_grant(grant):
            existing = self._repositories.capture_grants.get(grant.grant_id)
            if existing != grant:
                raise RuntimeError("capture grant request identity was reused")
            return existing
        return grant

    def capture_source(self, **values):
        return self._datasets.capture_source(**values)

    def generate(
        self, *, grant_id: str, source_id: str, teacher_model_ref: str,
        maximum_examples: int, confirmed: bool,
    ):
        if not confirmed:
            raise PermissionError("synthetic generation requires confirmation")
        model = self._catalog.get(teacher_model_ref)
        provenance = next(
            (
                item for item in self._catalog.provenances()
                if item.model_ref == teacher_model_ref
            ),
            None,
        )
        if model is None or provenance is None:
            raise PermissionError("teacher must be present in the signed active catalog")
        teacher = OllamaSyntheticTeacher(
            self._runtime, self._model_loader, model.model_ref,
            model.manifest_sha256,
        )
        return self._datasets.generate_proposals(
            grant_id=grant_id, source_id=source_id, teacher=teacher,
            maximum_examples=maximum_examples,
        )

    def review_example(
        self, *, request_id: str, grant_id: str, example_id: str,
        accepted: bool, confirmed: bool,
    ) -> SyntheticExampleReview:
        if not confirmed:
            raise PermissionError("human example review requires confirmation")
        example = next(
            (
                item for item in self._repositories.dataset_staging.examples(grant_id)
                if item.example_id == example_id
            ),
            None,
        )
        if example is None:
            raise KeyError("synthetic example is unavailable")
        evidence = hashlib.sha256(json.dumps({
            "accepted": accepted,
            "example_id": example_id,
            "generation_sha256": example.generation_sha256,
            "request_id": request_id,
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        review = SyntheticExampleReview(
            f"human-review-{request_id}", example_id, ExampleReviewKind.HUMAN,
            "local-owner", "acceptance.human.factory-example", evidence,
            accepted, self._now(),
        )
        return self._datasets.review(grant_id=grant_id, review=review)

    def seal_dataset(
        self, *, dataset_id: str, grant_id: str,
        near_duplicate_threshold_ppm: int, confirmed: bool,
    ):
        if not confirmed:
            raise PermissionError("dataset sealing requires confirmation")
        return self._datasets.seal(
            dataset_id=dataset_id, grant_id=grant_id,
            near_duplicate_threshold_ppm=near_duplicate_threshold_ppm,
        )

    def revoke_capture_grant(
        self, *, grant_id: str, expected_revision: int, reason_code: str,
        confirmed: bool,
    ):
        if not confirmed:
            raise PermissionError("capture grant revocation requires confirmation")
        return self._repositories.capture_grants.revoke(
            grant_id, expected_revision, reason_code, self._now(),
        )

    def issue_training_approval(self, **values):
        if self._training_approvals is None:
            raise RuntimeError("training approval service is unavailable")
        return self._training_approvals.issue(**values)

    def revoke_training_approval(self, **values):
        if self._training_approvals is None:
            raise RuntimeError("training approval service is unavailable")
        return self._training_approvals.revoke(**values)
