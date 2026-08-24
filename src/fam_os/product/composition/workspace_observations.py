"""Bounded deterministic map and retrieval observations for owner workspaces."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.linux.scoped_directories import ScopedDirectoryAdapter
from fam_os.adapters.linux.scoped_files import ScopedFileAdapter


_EXCLUDED_DIRECTORIES = {
    ".git", ".hg", ".mypy_cache", ".next", ".pytest_cache", ".ruff_cache",
    ".svn", ".venv", "__pycache__", "build", "coverage", "dist",
    "node_modules", "target", "venv",
}
_IMPORTANT_NAMES = {
    "agents.md": 1200,
    "agent.md": 1150,
    "readme.md": 1100,
    "readme": 1080,
    "package.json": 1050,
    "pyproject.toml": 1050,
    "cargo.toml": 1050,
    "go.mod": 1050,
    "requirements.txt": 1000,
    "dockerfile": 950,
    "docker-compose.yml": 940,
    "docker-compose.yaml": 940,
}
_TEXT_SUFFIXES = {
    ".c", ".cc", ".conf", ".cpp", ".cs", ".css", ".go", ".h", ".hpp",
    ".html", ".ini", ".java", ".js", ".json", ".jsx", ".md", ".mjs",
    ".php", ".properties", ".py", ".rb", ".rs", ".sh", ".sql", ".toml",
    ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
}
_QUERY_STOP_WORDS = {
    "about", "after", "also", "and", "can", "change", "create", "do",
    "for", "from", "implement", "in", "into", "it", "make", "my", "of",
    "on", "plan", "please", "project", "the", "this", "to", "workspace",
}


@dataclass(frozen=True, slots=True)
class WorkspaceObservationLimits:
    maximum_depth: int = 6
    maximum_directories: int = 128
    maximum_files: int = 512
    maximum_documents: int = 16
    maximum_document_bytes: int = 32_768
    maximum_total_document_bytes: int = 65_536


@dataclass(frozen=True, slots=True)
class _FileEntry:
    relative_path: str
    size_bytes: int


class WorkspaceObservationProvider:
    def __init__(
        self,
        directories: ScopedDirectoryAdapter,
        files: ScopedFileAdapter,
        limits: WorkspaceObservationLimits = WorkspaceObservationLimits(),
    ) -> None:
        self._directories = directories
        self._files = files
        self._limits = limits

    def map(self, workspace: Path) -> tuple[dict[str, object], str]:
        entries, truncated, directories_seen = self._inventory(workspace)
        payload: dict[str, object] = {
            "workspace": str(workspace),
            "files": [
                {"path": item.relative_path, "size_bytes": item.size_bytes}
                for item in entries
            ],
            "directories_scanned": directories_seen,
            "truncated": truncated,
            "bounds": self._bounds(),
        }
        return payload, _revision("map", payload["files"])

    def retrieve(
        self, workspace: Path, query: str,
    ) -> tuple[dict[str, object], str]:
        entries, inventory_truncated, _ = self._inventory(workspace)
        terms = _query_terms(query)
        ranked = sorted(
            (item for item in entries if _is_text_candidate(item)),
            key=lambda item: (-_score(item, terms), item.relative_path.casefold()),
        )
        documents: list[dict[str, object]] = []
        total_bytes = 0
        for item in ranked:
            if len(documents) >= self._limits.maximum_documents:
                break
            if item.size_bytes > self._limits.maximum_document_bytes:
                continue
            if total_bytes + item.size_bytes > self._limits.maximum_total_document_bytes:
                continue
            observed = self._files.observe(
                workspace / item.relative_path, include_content=True,
            )
            content = observed.content or b""
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                continue
            documents.append({
                "path": item.relative_path,
                "sha256": observed.sha256,
                "size_bytes": observed.size_bytes,
                "content": text,
            })
            total_bytes += observed.size_bytes
        payload: dict[str, object] = {
            "workspace": str(workspace),
            "query_terms": list(terms),
            "documents": documents,
            "inventory_truncated": inventory_truncated,
            "retrieval_truncated": len(ranked) > len(documents),
            "total_document_bytes": total_bytes,
            "bounds": self._bounds(),
        }
        revision_values = [
            {"path": item["path"], "sha256": item["sha256"]}
            for item in documents
        ]
        return payload, _revision("retrieve", revision_values)

    def _inventory(
        self, workspace: Path,
    ) -> tuple[tuple[_FileEntry, ...], bool, int]:
        observed = self._directories.observe(workspace)
        if not observed.exists:
            raise FileNotFoundError("workspace does not exist")
        queue = [(workspace, 0)]
        files: list[_FileEntry] = []
        directories_seen = 0
        truncated = False
        while queue and directories_seen < self._limits.maximum_directories:
            directory, depth = queue.pop(0)
            directories_seen += 1
            listing = self._directories.list_entries(directory, maximum_entries=1024)
            truncated = truncated or listing.truncated
            for entry in listing.entries:
                relative = (directory / entry.name).relative_to(workspace)
                if entry.kind == "directory":
                    if entry.name not in _EXCLUDED_DIRECTORIES:
                        if depth < self._limits.maximum_depth:
                            queue.append((directory / entry.name, depth + 1))
                        else:
                            truncated = True
                elif entry.kind == "file" and entry.size_bytes is not None:
                    files.append(_FileEntry(relative.as_posix(), entry.size_bytes))
                    if len(files) >= self._limits.maximum_files:
                        return tuple(files), True, directories_seen
        if queue:
            truncated = True
        return tuple(files), truncated, directories_seen

    def _bounds(self) -> dict[str, int]:
        return {
            "maximum_depth": self._limits.maximum_depth,
            "maximum_directories": self._limits.maximum_directories,
            "maximum_files": self._limits.maximum_files,
            "maximum_documents": self._limits.maximum_documents,
            "maximum_document_bytes": self._limits.maximum_document_bytes,
            "maximum_total_document_bytes": self._limits.maximum_total_document_bytes,
        }


def _query_terms(query: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        word for word in re.findall(r"[a-z0-9_.-]+", query.casefold())
        if len(word) > 2 and word not in _QUERY_STOP_WORDS
    ))[:32]


def _is_text_candidate(entry: _FileEntry) -> bool:
    path = Path(entry.relative_path)
    return (
        path.name.casefold() in _IMPORTANT_NAMES
        or path.suffix.casefold() in _TEXT_SUFFIXES
    )


def _score(entry: _FileEntry, terms: tuple[str, ...]) -> int:
    path = Path(entry.relative_path)
    normalized = entry.relative_path.casefold()
    score = _IMPORTANT_NAMES.get(path.name.casefold(), 0)
    score += sum(250 for term in terms if term in normalized)
    if path.parts and path.parts[0] in {"app", "lib", "src", "tests"}:
        score += 100
    score += max(0, 80 - 10 * (len(path.parts) - 1))
    return score


def _revision(kind: str, values: object) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return f"workspace-{kind}:sha256:{hashlib.sha256(payload).hexdigest()}"
