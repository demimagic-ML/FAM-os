"""Governed capture and split-before-synthesis dataset contracts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


FACTORY_DATASET_PROVENANCE_VERSION = "fam.factory.dataset-provenance/v1alpha1"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


class DatasetPartition(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    HELD_OUT = "held_out"


class TrainingSourceKind(StrEnum):
    VERIFIED_FIXTURE = "verified_fixture"
    OWNER_EXAMPLE = "owner_example"
    LICENSED_DATASET = "licensed_dataset"


class TrainingDataSensitivity(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    RESTRICTED = "restricted"


class HeldOutEvaluationKind(StrEnum):
    QUALITY = "quality"
    SAFETY = "safety"
    POLICY = "policy"
    UNRELATED = "unrelated"


class HeldOutVerifierKind(StrEnum):
    CONTAINS = "contains"
    EXACT_TEXT = "exact_text"
    SAFE_REFUSAL = "safe_refusal"
    HONEST_REFUSAL = "honest_refusal"


class ExampleReviewKind(StrEnum):
    DETERMINISTIC = "deterministic"
    HUMAN = "human"


@dataclass(frozen=True, slots=True)
class DatasetSplitPolicy:
    policy_id: str
    seed_sha256: str
    train_basis_points: int = 8_000
    validation_basis_points: int = 1_000
    held_out_basis_points: int = 1_000
    contract_version: str = FACTORY_DATASET_PROVENANCE_VERSION

    def __post_init__(self) -> None:
        _identifier(self.policy_id, "policy_id")
        _sha256(self.seed_sha256, "seed_sha256")
        values = (
            self.train_basis_points, self.validation_basis_points,
            self.held_out_basis_points,
        )
        if any(value < 1 for value in values) or sum(values) != 10_000:
            raise ValueError("dataset split basis points must be positive and total 10000")
        _version(self.contract_version)

    def assign(self, source_family_id: str) -> DatasetPartition:
        _identifier(source_family_id, "source_family_id")
        digest = hashlib.sha256(
            f"{self.seed_sha256}\0{source_family_id}".encode("utf-8"),
        ).digest()
        position = int.from_bytes(digest[:8], "big") % 10_000
        if position < self.train_basis_points:
            return DatasetPartition.TRAIN
        if position < self.train_basis_points + self.validation_basis_points:
            return DatasetPartition.VALIDATION
        return DatasetPartition.HELD_OUT


@dataclass(frozen=True, slots=True)
class TrainingCaptureGrant:
    grant_id: str
    proposal_id: str
    capability_id: str
    allowed_source_kinds: tuple[TrainingSourceKind, ...]
    workspace_scopes: tuple[str, ...]
    sensitivities: tuple[TrainingDataSensitivity, ...]
    maximum_source_bytes: int
    maximum_examples: int
    issued_at: datetime
    expires_at: datetime
    confirmed: bool
    revision: int = 1
    training_authorized: bool = False
    contract_version: str = FACTORY_DATASET_PROVENANCE_VERSION

    def __post_init__(self) -> None:
        for name in ("grant_id", "proposal_id", "capability_id"):
            _identifier(getattr(self, name), name)
        _unique_enum(self.allowed_source_kinds, TrainingSourceKind, "source kinds")
        _unique_enum(self.sensitivities, TrainingDataSensitivity, "sensitivities")
        if not self.workspace_scopes or len(self.workspace_scopes) > 32:
            raise ValueError("capture grant requires 1-32 workspace scopes")
        if any(not _bounded(value, 4_096) for value in self.workspace_scopes):
            raise ValueError("capture grant workspace scope is invalid")
        if not 1 <= self.maximum_source_bytes <= 64 * 1024 * 1024:
            raise ValueError("capture grant source-byte bound is invalid")
        if not 1 <= self.maximum_examples <= 100_000:
            raise ValueError("capture grant example bound is invalid")
        _aware(self.issued_at, "issued_at")
        _aware(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("capture grant expiry must follow issuance")
        if not self.confirmed:
            raise ValueError("training content capture requires explicit confirmation")
        if self.revision < 1:
            raise ValueError("capture grant revision must be positive")
        if self.training_authorized:
            raise ValueError("capture authority cannot authorize training")
        _version(self.contract_version)

    def permits(
        self, source_kind: TrainingSourceKind, workspace_scope: str,
        sensitivity: TrainingDataSensitivity, now: datetime,
    ) -> bool:
        _aware(now, "now")
        return (
            now < self.expires_at
            and source_kind in self.allowed_source_kinds
            and workspace_scope in self.workspace_scopes
            and sensitivity in self.sensitivities
        )


@dataclass(frozen=True, slots=True)
class TrainingCaptureRevocation:
    receipt_id: str
    grant_id: str
    previous_revision: int
    current_revision: int
    reason_code: str
    revoked_at: datetime
    contract_version: str = FACTORY_DATASET_PROVENANCE_VERSION

    def __post_init__(self) -> None:
        for name in ("receipt_id", "grant_id", "reason_code"):
            _identifier(getattr(self, name), name)
        if self.previous_revision < 1 or self.current_revision != self.previous_revision + 1:
            raise ValueError("capture revocation revision is invalid")
        _aware(self.revoked_at, "revoked_at")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class CapturedDatasetSource:
    source_id: str
    grant_id: str
    proposal_id: str
    source_family_id: str
    split_policy_id: str
    partition: DatasetPartition
    source_kind: TrainingSourceKind
    workspace_scope: str
    sensitivity: TrainingDataSensitivity
    license_id: str
    input_text: str
    reference_output: str | None
    captured_at: datetime
    content_sha256: str
    provenance_sha256: str
    evaluation_kind: HeldOutEvaluationKind | None = None
    evaluation_verifier: HeldOutVerifierKind | None = None
    evaluation_requirement_id: str | None = None
    contract_version: str = FACTORY_DATASET_PROVENANCE_VERSION

    def __post_init__(self) -> None:
        for name in (
            "source_id", "grant_id", "proposal_id", "source_family_id",
            "split_policy_id", "license_id",
        ):
            _identifier(getattr(self, name), name)
        if not isinstance(self.partition, DatasetPartition):
            raise ValueError("captured source partition is invalid")
        if not isinstance(self.source_kind, TrainingSourceKind):
            raise ValueError("captured source kind is invalid")
        if not isinstance(self.sensitivity, TrainingDataSensitivity):
            raise ValueError("captured source sensitivity is invalid")
        if not _bounded(self.workspace_scope, 4_096):
            raise ValueError("captured source workspace scope is invalid")
        if not _bounded(self.input_text, 131_072):
            raise ValueError("captured source input is invalid")
        if self.reference_output is not None and not _bounded(
            self.reference_output, 131_072,
        ):
            raise ValueError("captured source reference output is invalid")
        evaluation_values = (
            self.evaluation_kind, self.evaluation_verifier,
            self.evaluation_requirement_id,
        )
        if any(value is not None for value in evaluation_values):
            if (
                not isinstance(self.evaluation_kind, HeldOutEvaluationKind)
                or not isinstance(self.evaluation_verifier, HeldOutVerifierKind)
                or self.evaluation_requirement_id is None
            ):
                raise ValueError("held-out evaluation metadata must be complete")
            _identifier(
                self.evaluation_requirement_id, "evaluation_requirement_id",
            )
        _aware(self.captured_at, "captured_at")
        _sha256(self.content_sha256, "content_sha256")
        _sha256(self.provenance_sha256, "provenance_sha256")
        if self.content_sha256 != captured_source_content_digest(self):
            raise ValueError("captured source content digest does not match")
        if self.provenance_sha256 != captured_source_provenance_digest(self):
            raise ValueError("captured source provenance digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class SyntheticExampleProposal:
    example_id: str
    source_id: str
    source_family_id: str
    partition: DatasetPartition
    teacher_model_ref: str
    teacher_manifest_sha256: str
    input_text: str
    completion: str
    generated_at: datetime
    content_sha256: str
    generation_sha256: str
    accepted_for_dataset: bool = False
    contract_version: str = FACTORY_DATASET_PROVENANCE_VERSION

    def __post_init__(self) -> None:
        for name in (
            "example_id", "source_id", "source_family_id", "teacher_model_ref",
        ):
            _identifier(getattr(self, name), name)
        if self.partition is DatasetPartition.HELD_OUT:
            raise ValueError("teacher generation cannot consume held-out sources")
        _sha256(self.teacher_manifest_sha256, "teacher_manifest_sha256")
        if not _bounded(self.input_text, 131_072) or not _bounded(
            self.completion, 131_072,
        ):
            raise ValueError("synthetic example content is invalid")
        _aware(self.generated_at, "generated_at")
        _sha256(self.content_sha256, "content_sha256")
        _sha256(self.generation_sha256, "generation_sha256")
        if self.content_sha256 != synthetic_example_content_digest(self):
            raise ValueError("synthetic example content digest does not match")
        if self.generation_sha256 != synthetic_example_generation_digest(self):
            raise ValueError("synthetic example generation digest does not match")
        if self.accepted_for_dataset:
            raise ValueError("unreviewed synthetic examples cannot enter a dataset")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class SyntheticExampleReview:
    review_id: str
    example_id: str
    review_kind: ExampleReviewKind
    reviewer_id: str
    acceptance_id: str
    evidence_sha256: str
    accepted: bool
    reviewed_at: datetime
    contract_version: str = FACTORY_DATASET_PROVENANCE_VERSION

    def __post_init__(self) -> None:
        for name in ("review_id", "example_id", "reviewer_id", "acceptance_id"):
            _identifier(getattr(self, name), name)
        if not isinstance(self.review_kind, ExampleReviewKind):
            raise ValueError("synthetic example review kind is invalid")
        _sha256(self.evidence_sha256, "evidence_sha256")
        _aware(self.reviewed_at, "reviewed_at")
        _version(self.contract_version)


def build_captured_source(
    *, source_id: str, grant_id: str, proposal_id: str,
    source_family_id: str, split_policy: DatasetSplitPolicy,
    source_kind: TrainingSourceKind, workspace_scope: str,
    sensitivity: TrainingDataSensitivity, license_id: str, input_text: str,
    reference_output: str | None, captured_at: datetime,
    evaluation_kind: HeldOutEvaluationKind | None = None,
    evaluation_verifier: HeldOutVerifierKind | None = None,
    evaluation_requirement_id: str | None = None,
) -> CapturedDatasetSource:
    evaluation = (
        evaluation_kind, evaluation_verifier, evaluation_requirement_id,
    )
    if any(value is not None for value in evaluation) and any(
        value is None for value in evaluation
    ):
        raise ValueError("held-out evaluation metadata must be complete")
    values = dict(
        source_id=source_id, grant_id=grant_id, proposal_id=proposal_id,
        source_family_id=source_family_id, split_policy_id=split_policy.policy_id,
        partition=split_policy.assign(source_family_id), source_kind=source_kind,
        workspace_scope=workspace_scope, sensitivity=sensitivity,
        license_id=license_id, input_text=input_text,
        reference_output=reference_output, captured_at=captured_at,
        evaluation_kind=evaluation_kind,
        evaluation_verifier=evaluation_verifier,
        evaluation_requirement_id=evaluation_requirement_id,
    )
    return CapturedDatasetSource(
        source_id, grant_id, proposal_id, source_family_id,
        split_policy.policy_id, split_policy.assign(source_family_id), source_kind,
        workspace_scope, sensitivity, license_id, input_text, reference_output,
        captured_at, _captured_content_digest(values),
        _captured_provenance_digest(values),
        evaluation_kind, evaluation_verifier, evaluation_requirement_id,
    )


def captured_source_content_digest(source: CapturedDatasetSource) -> str:
    return _captured_content_digest({
        name: getattr(source, name) for name in CapturedDatasetSource.__dataclass_fields__
    })


def captured_source_provenance_digest(source: CapturedDatasetSource) -> str:
    return _captured_provenance_digest({
        name: getattr(source, name) for name in CapturedDatasetSource.__dataclass_fields__
    })


def build_synthetic_example(
    *, source: CapturedDatasetSource, teacher_model_ref: str,
    teacher_manifest_sha256: str, input_text: str, completion: str,
    generated_at: datetime, ordinal: int,
) -> SyntheticExampleProposal:
    if source.partition is DatasetPartition.HELD_OUT:
        raise ValueError("teacher generation cannot consume held-out sources")
    if ordinal < 1:
        raise ValueError("synthetic example ordinal must be positive")
    content_sha256 = _digest({"completion": completion, "input_text": input_text})
    example_id = f"synthetic-{_digest({
        'content_sha256': content_sha256,
        'ordinal': ordinal,
        'source_id': source.source_id,
        'teacher_manifest_sha256': teacher_manifest_sha256,
        'teacher_model_ref': teacher_model_ref,
    })}"
    values = dict(
        example_id=example_id, source_id=source.source_id,
        source_family_id=source.source_family_id, partition=source.partition,
        teacher_model_ref=teacher_model_ref,
        teacher_manifest_sha256=teacher_manifest_sha256,
        input_text=input_text, completion=completion, generated_at=generated_at,
        content_sha256=content_sha256,
    )
    return SyntheticExampleProposal(
        example_id, source.source_id, source.source_family_id, source.partition,
        teacher_model_ref, teacher_manifest_sha256, input_text, completion,
        generated_at, content_sha256, _synthetic_generation_values_digest(values),
    )


def synthetic_example_content_digest(example: SyntheticExampleProposal) -> str:
    return _digest({"completion": example.completion, "input_text": example.input_text})


def synthetic_example_generation_digest(example: SyntheticExampleProposal) -> str:
    return _synthetic_generation_values_digest({
        name: getattr(example, name)
        for name in SyntheticExampleProposal.__dataclass_fields__
    })


def _synthetic_generation_values_digest(values) -> str:
    return _digest({
        "content_sha256": values["content_sha256"],
        "example_id": values["example_id"],
        "generated_at": values["generated_at"].isoformat(),
        "partition": values["partition"].value,
        "source_family_id": values["source_family_id"],
        "source_id": values["source_id"],
        "teacher_manifest_sha256": values["teacher_manifest_sha256"],
        "teacher_model_ref": values["teacher_model_ref"],
    })


def _captured_content_digest(values) -> str:
    content = {
        "input_text": values["input_text"],
        "reference_output": values["reference_output"],
    }
    if values.get("evaluation_kind") is not None:
        content.update({
            "evaluation_kind": values["evaluation_kind"].value,
            "evaluation_requirement_id": values["evaluation_requirement_id"],
            "evaluation_verifier": values["evaluation_verifier"].value,
        })
    return _digest(content)


def _captured_provenance_digest(values) -> str:
    captured_at = values["captured_at"]
    return _digest({
        "captured_at": captured_at.isoformat(),
        "content_sha256": _captured_content_digest(values),
        "grant_id": values["grant_id"],
        "license_id": values["license_id"],
        "partition": values["partition"].value,
        "proposal_id": values["proposal_id"],
        "sensitivity": values["sensitivity"].value,
        "source_family_id": values["source_family_id"],
        "source_id": values["source_id"],
        "source_kind": values["source_kind"].value,
        "split_policy_id": values["split_policy_id"],
        "workspace_scope": values["workspace_scope"],
    })


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} is invalid")


def _sha256(value: str, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{name} must be lowercase SHA-256")


def _bounded(value: str, maximum: int) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\x00" not in value and len(value) <= maximum


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _unique_enum(values, expected, name: str) -> None:
    if not values or len(set(values)) != len(values) or any(
        not isinstance(value, expected) for value in values
    ):
        raise ValueError(f"capture grant {name} must be nonempty and unique")


def _version(value: str) -> None:
    if value != FACTORY_DATASET_PROVENANCE_VERSION:
        raise ValueError("unsupported factory dataset provenance version")
