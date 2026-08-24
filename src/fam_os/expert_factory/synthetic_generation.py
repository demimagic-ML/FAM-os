"""Ports for bounded teacher generation and independent example review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fam_os.expert_factory.dataset_provenance import (
    CapturedDatasetSource,
    SyntheticExampleProposal,
    SyntheticExampleReview,
)


@dataclass(frozen=True, slots=True)
class GeneratedExampleContent:
    input_text: str
    completion: str

    def __post_init__(self) -> None:
        if not self.input_text.strip() or not self.completion.strip():
            raise ValueError("teacher output must contain input and completion")
        if len(self.input_text) > 131_072 or len(self.completion) > 131_072:
            raise ValueError("teacher output exceeds the dataset content bound")


class SyntheticTeacher(Protocol):
    model_ref: str
    manifest_sha256: str

    def generate(
        self, source: CapturedDatasetSource, maximum_examples: int,
    ) -> tuple[GeneratedExampleContent, ...]: ...


class SyntheticExampleReviewer(Protocol):
    def review(self, example: SyntheticExampleProposal) -> SyntheticExampleReview: ...
