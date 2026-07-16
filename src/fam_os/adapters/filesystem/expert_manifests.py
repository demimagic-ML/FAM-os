"""Bounded, read-only expert-manifest directory source."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.filesystem.bounded_documents import read_bounded_regular_utf8
from fam_os.experts.manifest import ExpertManifest
from fam_os.schemas import loads_document


@dataclass(frozen=True, slots=True)
class DirectoryExpertManifestSource:
    root: Path
    maximum_manifests: int = 1024
    maximum_document_bytes: int = 1024 * 1024

    def __post_init__(self) -> None:
        if self.maximum_manifests <= 0 or self.maximum_document_bytes <= 0:
            raise ValueError("expert manifest source bounds must be positive")

    def load(self) -> tuple[ExpertManifest, ...]:
        if not self.root.is_dir():
            raise FileNotFoundError("expert manifest directory is unavailable")
        paths = tuple(sorted(self.root.glob("*.json")))
        if len(paths) > self.maximum_manifests:
            raise ValueError("expert manifest directory exceeds file limit")
        return tuple(self._load_file(path) for path in paths)

    def _load_file(self, path: Path) -> ExpertManifest:
        serialized = read_bounded_regular_utf8(path, self.maximum_document_bytes)
        value = loads_document(serialized)
        if not isinstance(value, ExpertManifest):
            raise ValueError("expert manifest directory contains a non-current document")
        return value
