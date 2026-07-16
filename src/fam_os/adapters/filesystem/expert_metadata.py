"""Bounded strict directory sources for expert routing and benchmark metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.filesystem.bounded_documents import read_bounded_regular_utf8
from fam_os.experts.benchmark_metadata import ExpertBenchmarkRun
from fam_os.experts.routing_metadata import ExpertRoutingEmbedding
from fam_os.schemas import loads_document


@dataclass(frozen=True, slots=True)
class DirectoryExpertRoutingEmbeddingSource:
    root: Path
    maximum_documents: int = 4096
    maximum_document_bytes: int = 2 * 1024 * 1024

    def __post_init__(self) -> None:
        _require_bounds(self.maximum_documents, self.maximum_document_bytes)

    def load(self) -> tuple[ExpertRoutingEmbedding, ...]:
        return tuple(_load_directory(
            self.root, self.maximum_documents, self.maximum_document_bytes,
            ExpertRoutingEmbedding,
        ))


@dataclass(frozen=True, slots=True)
class DirectoryExpertBenchmarkSource:
    root: Path
    maximum_documents: int = 16_384
    maximum_document_bytes: int = 4 * 1024 * 1024

    def __post_init__(self) -> None:
        _require_bounds(self.maximum_documents, self.maximum_document_bytes)

    def load(self) -> tuple[ExpertBenchmarkRun, ...]:
        return tuple(_load_directory(
            self.root, self.maximum_documents, self.maximum_document_bytes,
            ExpertBenchmarkRun,
        ))


def _load_directory(root, maximum_documents, maximum_bytes, expected_type):
    if not root.is_dir():
        raise FileNotFoundError("expert metadata directory is unavailable")
    paths = tuple(sorted(root.glob("*.json")))
    if len(paths) > maximum_documents:
        raise ValueError("expert metadata directory exceeds file limit")
    for path in paths:
        serialized = read_bounded_regular_utf8(path, maximum_bytes)
        value = loads_document(serialized)
        if not isinstance(value, expected_type):
            raise ValueError("expert metadata directory contains a wrong document type")
        yield value


def _require_bounds(maximum_documents, maximum_bytes):
    if maximum_documents <= 0 or maximum_bytes <= 0:
        raise ValueError("expert metadata source bounds must be positive")
