"""Bounded no-link source context from an isolated candidate workspace."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re

from fam_os.adapters.filesystem.candidate_io import read_regular, reject_tree_symlinks
from fam_os.core.engineering.candidate_generation import (
    CandidateContextDocument, CandidateGenerationContext,
)
from fam_os.core.engineering.transactions import CandidateWorkspace


_IGNORED_DIRECTORIES = frozenset({
    ".git", ".fam", ".venv", "venv", "node_modules", "target", "dist",
    "build", "__pycache__", ".next", ".cache", "coverage",
})
_SOURCE_SUFFIXES = frozenset({
    ".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java", ".kt",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".sh", ".html", ".css", ".scss",
    ".json", ".toml", ".yaml", ".yml", ".md", ".sql", ".xml", ".txt",
})
_SECRET_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".kdbx"})
_SECRET_NAMES = frozenset({
    ".env", "credentials", "credentials.json", "secrets.json",
    "id_rsa", "id_ed25519", ".npmrc", ".pypirc", "netrc", ".netrc",
})
_SECRET_CONTENT = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bAKIA[A-Z0-9]{16}\b|"
    r"(?i:\b(?:api[_-]?key|access[_-]?token|password|client[_-]?secret)\b)"
    r"\s*[:=]\s*[\"'][^\"'\r\n]{8,}[\"']",
)


class BoundedCandidateContextReader:
    def __init__(
        self, *, maximum_depth: int = 12, maximum_inventory_files: int = 512,
        maximum_documents: int = 48, maximum_file_bytes: int = 32_768,
        maximum_document_bytes: int = 131_072,
    ) -> None:
        values = (
            maximum_depth, maximum_inventory_files, maximum_documents,
            maximum_file_bytes, maximum_document_bytes,
        )
        if any(value <= 0 for value in values):
            raise ValueError("candidate context bounds must be positive")
        self.maximum_depth = maximum_depth
        self.maximum_inventory_files = maximum_inventory_files
        self.maximum_documents = maximum_documents
        self.maximum_file_bytes = maximum_file_bytes
        self.maximum_document_bytes = maximum_document_bytes

    def read(
        self, candidate: CandidateWorkspace, query: str,
        preferred_paths: tuple[str, ...] = (),
    ) -> CandidateGenerationContext:
        root = Path(candidate.candidate_workspace)
        if not root.is_absolute() or root.name != "workspace" or root.parent.name != candidate.candidate_id:
            raise PermissionError("candidate context workspace identity is invalid")
        reject_tree_symlinks(root, _IGNORED_DIRECTORIES)
        paths, truncated = self._inventory(root)
        documents, document_truncated = self._documents(
            root, paths, query, preferred_paths,
        )
        return CandidateGenerationContext(
            candidate.candidate_id, candidate.baseline_tree_sha256, paths,
            documents, truncated or document_truncated,
        )

    def _inventory(self, root: Path) -> tuple[tuple[str, ...], bool]:
        values: list[str] = []
        truncated = False
        for current, directories, files in os.walk(root, followlinks=False):
            relative = Path(current).relative_to(root)
            depth = len(relative.parts)
            directories[:] = sorted(
                item for item in directories if item not in _IGNORED_DIRECTORIES
            )
            if depth >= self.maximum_depth:
                truncated = truncated or bool(directories)
                directories[:] = []
            for name in sorted(files):
                path = Path(current) / name
                item = path.relative_to(root).as_posix()
                if _sensitive_path(item):
                    continue
                if len(values) >= self.maximum_inventory_files:
                    truncated = True
                    continue
                values.append(item)
        return tuple(sorted(values)), truncated

    def _documents(self, root, paths, query, preferred_paths):
        preferred = set(preferred_paths)
        terms = tuple(dict.fromkeys(re.findall(r"[a-z0-9_.-]{3,}", query.casefold())))[:32]
        ranked = sorted(
            paths,
            key=lambda path: (-_score(path, preferred, terms), path),
        )
        values: list[CandidateContextDocument] = []
        used = 0
        eligible = 0
        for relative in ranked:
            path = root / relative
            try:
                size = path.stat(follow_symlinks=False).st_size
            except OSError:
                raise RuntimeError("candidate context changed during observation")
            if size > self.maximum_file_bytes or Path(relative).suffix.casefold() not in _SOURCE_SUFFIXES:
                continue
            eligible += 1
            if len(values) >= self.maximum_documents or used + size > self.maximum_document_bytes:
                continue
            content = read_regular(path, self.maximum_file_bytes)
            if _SECRET_CONTENT.search(content.decode("utf-8", "replace")):
                continue
            try:
                decoded = content.decode("utf-8", "strict")
            except UnicodeDecodeError:
                continue
            values.append(CandidateContextDocument(
                relative, hashlib.sha256(content).hexdigest(), decoded,
            ))
            used += len(content)
        return tuple(values), eligible > len(values)


def _score(path: str, preferred: set[str], terms: tuple[str, ...]) -> int:
    folded = path.casefold()
    score = 100 if path in preferred else 0
    score += sum(10 for term in terms if term in folded)
    if Path(path).suffix.casefold() in _SOURCE_SUFFIXES:
        score += 2
    if Path(path).name in {"pyproject.toml", "package.json", "Cargo.toml", "go.mod"}:
        score += 5
    return score


def _sensitive_path(relative: str) -> bool:
    path = Path(relative)
    name = path.name.casefold()
    return (
        name in _SECRET_NAMES
        or name.startswith(".env.")
        or path.suffix.casefold() in _SECRET_SUFFIXES
        or any(part.casefold() in {".ssh", ".gnupg"} for part in path.parts)
    )
