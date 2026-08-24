"""Typed design-system, creative-asset, and verification contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, digest, positive, relative_path, text, texts
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class DesignAssetKind(StrEnum):
    RASTER = "raster"
    SVG = "svg"
    ICON = "icon"
    DIAGRAM = "diagram"
    ANIMATION = "animation"
    MEDIA = "media"


class DesignVerificationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


@dataclass(frozen=True, slots=True)
class DesignToken:
    token_id: str
    category: str
    value: str
    description: str

    def __post_init__(self) -> None:
        for name in ("token_id", "category", "value", "description"):
            text(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class DesignComponent:
    component_id: str
    architecture_element_ids: tuple[str, ...]
    responsive_states: tuple[str, ...]
    interaction_specifications: tuple[str, ...]
    accessibility_requirements: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.component_id, "component_id")
        for values, name in (
            (self.architecture_element_ids, "architecture element IDs"),
            (self.responsive_states, "responsive states"),
            (self.interaction_specifications, "interaction specifications"),
            (self.accessibility_requirements, "accessibility requirements"),
        ):
            texts(values, name)


@dataclass(frozen=True, slots=True)
class DesignBrief:
    brief_id: str
    task_id: str
    title: str
    audiences: tuple[str, ...]
    goals: tuple[str, ...]
    constraints: tuple[str, ...]
    tokens: tuple[DesignToken, ...]
    components: tuple[DesignComponent, ...]
    reference_asset_ids: tuple[str, ...]
    approved_at: datetime
    human_preview_required: bool = True
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("brief_id", "task_id", "title"):
            text(getattr(self, name), name)
        for values, name in (
            (self.audiences, "audiences"), (self.goals, "goals"),
            (self.constraints, "constraints"),
        ):
            texts(values, name)
        if len({item.token_id for item in self.tokens}) != len(self.tokens):
            raise ValueError("design token IDs must be unique")
        if len({item.component_id for item in self.components}) != len(self.components):
            raise ValueError("design component IDs must be unique")
        texts(self.reference_asset_ids, "reference asset IDs")
        aware(self.approved_at, "approved_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("design brief contract version is unsupported")


@dataclass(frozen=True, slots=True)
class DesignAssetRecord:
    asset_id: str
    brief_id: str
    candidate_id: str
    relative_path: str
    kind: DesignAssetKind
    mime_type: str
    sha256: str
    source_asset_ids: tuple[str, ...]
    reference_asset_ids: tuple[str, ...]
    model_or_tool_id: str
    model_or_tool_version: str
    prompt_sha256: str | None
    width: int
    height: int
    color_profile: str
    license_expression: str
    provenance_id: str
    metadata_stripped: bool
    created_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "asset_id", "brief_id", "candidate_id", "mime_type",
            "model_or_tool_id", "model_or_tool_version", "color_profile",
            "license_expression", "provenance_id",
        ):
            text(getattr(self, name), name)
        relative_path(self.relative_path, "asset path")
        digest(self.sha256, "sha256", required=True)
        digest(self.prompt_sha256, "prompt_sha256")
        texts(self.source_asset_ids, "source asset IDs")
        texts(self.reference_asset_ids, "reference asset IDs")
        positive(self.width, "width")
        positive(self.height, "height")
        aware(self.created_at, "created_at")
        if not self.metadata_stripped:
            raise ValueError("published design assets must have hidden metadata stripped")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("design asset contract version is unsupported")


@dataclass(frozen=True, slots=True)
class DesignVerificationReceipt:
    receipt_id: str
    brief_id: str
    candidate_id: str
    asset_ids: tuple[str, ...]
    format_evidence_ids: tuple[str, ...]
    svg_sanitization_ids: tuple[str, ...]
    metadata_evidence_ids: tuple[str, ...]
    font_license_evidence_ids: tuple[str, ...]
    contrast_evidence_ids: tuple[str, ...]
    accessibility_evidence_ids: tuple[str, ...]
    responsive_capture_sha256: tuple[str, ...]
    visual_difference_ratio: float
    visual_threshold: float
    human_checkpoint_id: str | None
    status: DesignVerificationStatus
    verified_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("receipt_id", "brief_id", "candidate_id"):
            text(getattr(self, name), name)
        texts(self.asset_ids, "asset IDs")
        for values, name in (
            (self.format_evidence_ids, "format evidence IDs"),
            (self.metadata_evidence_ids, "metadata evidence IDs"),
            (self.contrast_evidence_ids, "contrast evidence IDs"),
            (self.accessibility_evidence_ids, "accessibility evidence IDs"),
        ):
            texts(values, name)
        for value in self.responsive_capture_sha256:
            digest(value, "responsive capture digest", required=True)
        if not 0 <= self.visual_difference_ratio <= 1 or not 0 <= self.visual_threshold <= 1:
            raise ValueError("visual ratios must be between zero and one")
        if self.visual_difference_ratio > self.visual_threshold and self.status is DesignVerificationStatus.PASSED:
            raise ValueError("visual regression above threshold cannot pass")
        if self.human_checkpoint_id is not None:
            text(self.human_checkpoint_id, "human_checkpoint_id")
        if self.status is DesignVerificationStatus.PASSED and self.human_checkpoint_id is None:
            raise ValueError("passing design verification requires human preview checkpoint")
        aware(self.verified_at, "verified_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("design verification contract version is unsupported")
