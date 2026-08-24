"""Governed documentation, generated-content, and traceability contracts."""

import base64
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, digest, relative_path, text, texts
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class DocumentationArtifactKind(StrEnum):
    DIAGRAM = "diagram"
    API_REFERENCE = "api_reference"
    RUNBOOK = "runbook"
    CHANGELOG = "changelog"
    GENERATED_CODE = "generated_code"


@dataclass(frozen=True, slots=True)
class SignedDocumentationRecipe:
    recipe_id: str
    recipe_version: str
    kind: DocumentationArtifactKind
    generator_id: str
    output_media_type: str
    maximum_source_files: int
    maximum_source_bytes: int
    maximum_output_bytes: int
    signer_key_id: str
    payload_sha256: str
    signature_base64: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "recipe_id", "recipe_version", "generator_id",
            "output_media_type", "signer_key_id", "signature_base64",
        ):
            text(getattr(self, name), name)
        if "/" not in self.output_media_type or any(
            character.isspace() for character in self.output_media_type
        ):
            raise ValueError("documentation recipe output media type is invalid")
        for name in (
            "maximum_source_files", "maximum_source_bytes",
            "maximum_output_bytes",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        digest(self.payload_sha256, "payload_sha256", required=True)
        try:
            signature = base64.b64decode(self.signature_base64, validate=True)
        except (TypeError, ValueError) as error:
            raise ValueError("documentation recipe signature must be strict base64") from error
        if len(signature) != 64:
            raise ValueError("documentation recipe signature must be Ed25519")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("documentation recipe contract version is unsupported")

    @property
    def coordinate(self) -> str:
        return f"{self.recipe_id}@{self.recipe_version}"


class RequirementTraceStatus(StrEnum):
    SATISFIED = "satisfied"
    PARTIAL = "partial"
    UNSATISFIED = "unsatisfied"


@dataclass(frozen=True, slots=True)
class DocumentationRequirementSelection:
    selection_id: str
    task_id: str
    candidate_id: str
    policy_id: str
    intent_sha256: str
    required_kinds: tuple[DocumentationArtifactKind, ...]
    evaluated_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("selection_id", "task_id", "candidate_id", "policy_id"):
            text(getattr(self, name), name)
        digest(self.intent_sha256, "intent_sha256", required=True)
        if len(self.required_kinds) != len(set(self.required_kinds)):
            raise ValueError("documentation required kinds must be unique")
        aware(self.evaluated_at, "evaluated_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("documentation requirement selection version is unsupported")


@dataclass(frozen=True, slots=True)
class DocumentationSource:
    path: str
    content_sha256: str

    def __post_init__(self) -> None:
        relative_path(self.path, "documentation source path")
        digest(self.content_sha256, "documentation source digest", required=True)


@dataclass(frozen=True, slots=True)
class DocumentationGenerationRequest:
    request_id: str
    task_id: str
    candidate_id: str
    kind: DocumentationArtifactKind
    output_path: str
    generator_recipe_id: str
    ownership_path: str
    regeneration_instruction_path: str
    sources: tuple[DocumentationSource, ...]
    created_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("request_id", "task_id", "candidate_id", "generator_recipe_id"):
            text(getattr(self, name), name)
        for name in ("output_path", "ownership_path", "regeneration_instruction_path"):
            relative_path(getattr(self, name), name)
        if not self.sources or len({item.path for item in self.sources}) != len(self.sources):
            raise ValueError("documentation generation sources are invalid")
        if self.output_path in {item.path for item in self.sources}:
            raise ValueError("generated documentation cannot be its own source")
        aware(self.created_at, "created_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("documentation generation version is unsupported")


@dataclass(frozen=True, slots=True)
class DocumentationGovernanceBinding:
    binding_id: str
    request_id: str
    task_id: str
    candidate_id: str
    governance_sources: tuple[DocumentationSource, ...]
    bound_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("binding_id", "request_id", "task_id", "candidate_id"):
            text(getattr(self, name), name)
        paths = tuple(item.path for item in self.governance_sources)
        if not paths or paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("documentation governance sources must be unique and sorted")
        aware(self.bound_at, "bound_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("documentation governance binding version is unsupported")


@dataclass(frozen=True, slots=True)
class GeneratedDocumentationReceipt:
    receipt_id: str
    request_id: str
    task_id: str
    candidate_id: str
    output_path: str
    output_sha256: str
    generator_recipe_id: str
    sources: tuple[DocumentationSource, ...]
    generated_at: datetime
    authoritative_regeneration: bool
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("receipt_id", "request_id", "task_id", "candidate_id", "generator_recipe_id"):
            text(getattr(self, name), name)
        relative_path(self.output_path, "output_path")
        digest(self.output_sha256, "output_sha256", required=True)
        if not self.sources:
            raise ValueError("generated documentation receipt requires sources")
        aware(self.generated_at, "generated_at")
        if not self.authoritative_regeneration:
            raise ValueError("generated documentation must declare authoritative regeneration")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("generated documentation receipt version is unsupported")


@dataclass(frozen=True, slots=True)
class DocumentationStalenessReport:
    report_id: str
    receipt_id: str
    task_id: str
    observed_at: datetime
    stale_source_paths: tuple[str, ...]
    missing_source_paths: tuple[str, ...]
    output_modified: bool
    stale: bool
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("report_id", "receipt_id", "task_id"):
            text(getattr(self, name), name)
        aware(self.observed_at, "observed_at")
        texts(self.stale_source_paths, "stale_source_paths")
        texts(self.missing_source_paths, "missing_source_paths")
        if self.stale != bool(self.stale_source_paths or self.missing_source_paths or self.output_modified):
            raise ValueError("documentation staleness conclusion is inconsistent")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("documentation staleness version is unsupported")


@dataclass(frozen=True, slots=True)
class RequirementTraceabilityRecord:
    trace_id: str
    task_id: str
    requirement_id: str
    requirement_source_path: str
    implementation_paths: tuple[str, ...]
    test_paths: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    status: RequirementTraceStatus
    recorded_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("trace_id", "task_id", "requirement_id"):
            text(getattr(self, name), name)
        relative_path(self.requirement_source_path, "requirement_source_path")
        for name in ("implementation_paths", "test_paths"):
            values = getattr(self, name)
            texts(values, name)
            for value in values:
                relative_path(value, f"{name} item")
        texts(self.evidence_ids, "evidence_ids")
        if self.status is RequirementTraceStatus.SATISFIED and (
            not self.implementation_paths or not self.test_paths or not self.evidence_ids
        ):
            raise ValueError("satisfied requirement lacks implementation test or evidence")
        aware(self.recorded_at, "recorded_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("requirement traceability version is unsupported")
