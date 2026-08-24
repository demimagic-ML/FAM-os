"""Bounded read-only repository evidence from an exact owner workspace."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

from fam_os.adapters.filesystem.candidate_io import read_regular, reject_tree_symlinks
from fam_os.adapters.git import LocalGitAdapter
from fam_os.core.engineering.repository import (
    RepositoryArchitectureRule, RepositoryContextRecord,
    RepositoryContextTrust, RepositoryEvidenceBundle, RepositoryFile,
    RepositoryFileRole, RepositoryGitState, RepositoryManifest,
    RepositoryObservationBounds, RepositorySourceKind,
)


_EXCLUDED = frozenset({
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "target",
    "build", "dist", "__pycache__", ".next", ".cache", ".terraform",
    ".gradle", ".turbo", ".parcel-cache", "coverage",
})
_CONTEXT_NAMES = {"AGENTS.md", "README.md", "MASTER_PLAN.md", "MASTER_PLANv2.md"}
_MANIFESTS = {"pyproject.toml", "package.json", "Cargo.toml", "go.mod", "pom.xml", "build.gradle"}


class BoundedFilesystemRepositoryObserver:
    def __init__(
        self, *, maximum_files=2_000, maximum_file_bytes=8_388_608,
        maximum_total_bytes=268_435_456, maximum_context_records=16,
        maximum_context_bytes=65_536, git=None, clock=None,
    ) -> None:
        self._maximum_files = maximum_files
        self._maximum_file_bytes = maximum_file_bytes
        self._maximum_total_bytes = maximum_total_bytes
        self._maximum_context_records = maximum_context_records
        self._maximum_context_bytes = maximum_context_bytes
        self._git = git or LocalGitAdapter()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def observe(self, task_id: str, workspace_root: str) -> RepositoryEvidenceBundle:
        selected = Path(workspace_root).resolve(strict=True)
        if str(selected) != workspace_root or selected.is_symlink():
            raise PermissionError("repository root must be exact and canonical")
        resolver = getattr(self._git, "repository_root", None)
        try:
            root = selected if resolver is None else resolver(selected)
            git_observation = self._git.observe(task_id, root)
        except (RuntimeError, ValueError):
            # A workspace is useful even when it is not version-controlled. Git
            # capability is discovered, not inferred from a .git-shaped path.
            root = selected
            git_observation = None
        reject_tree_symlinks(root, _EXCLUDED)
        files, contexts, manifests, total, truncated = self._scan(root)
        revision = _revision(
            files,
            None if git_observation is None else git_observation.head_object_id,
            None if git_observation is None else git_observation.diff_sha256,
        )
        rules = tuple(
            RepositoryArchitectureRule(
                f"rule-{item.record_id}", item.path,
                "Repository instruction content is untrusted and must be evaluated by Core policy.",
                RepositoryContextTrust.UNTRUSTED_CONTEXT,
            )
            for item in contexts if Path(item.path).name == "AGENTS.md"
        )
        return RepositoryEvidenceBundle(
            f"repository-bundle-{uuid4().hex}", task_id, self._clock(), str(root),
            revision, tuple(files), tuple(contexts), (), (), (), tuple(manifests),
            (), _git_state(git_observation), rules,
            RepositoryObservationBounds(
                self._maximum_files, self._maximum_context_records, 1, 1, 1,
                self._maximum_context_bytes,
            ), truncated or total >= self._maximum_total_bytes,
        )

    def _scan(self, root):
        files, contexts, manifests = [], [], []
        total = 0
        context_total = 0
        truncated = False
        for current, directories, names in os.walk(root, followlinks=False):
            directories[:] = sorted(
                name for name in directories if name not in _EXCLUDED
            )
            for name in sorted(names):
                path = Path(current) / name
                relative = path.relative_to(root)
                if len(files) >= self._maximum_files:
                    truncated = True
                    break
                size = path.stat(follow_symlinks=False).st_size
                if size > self._maximum_file_bytes or total + size > self._maximum_total_bytes:
                    truncated = True
                    continue
                content = read_regular(path, self._maximum_file_bytes)
                total += len(content)
                relative_text = relative.as_posix()
                digest = hashlib.sha256(content).hexdigest()
                files.append(RepositoryFile(
                    relative_text, digest, len(content), _role(relative),
                    _language(relative),
                ))
                if path.name in _CONTEXT_NAMES and len(contexts) < self._maximum_context_records:
                    remaining = self._maximum_context_bytes - context_total
                    text = _text(content, remaining)
                    if text:
                        contexts.append(RepositoryContextRecord(
                            f"context-{hashlib.sha256(relative_text.encode()).hexdigest()[:16]}",
                            RepositorySourceKind.REPOSITORY_INSTRUCTION,
                            relative_text, digest, text, False,
                        ))
                        context_total += len(content)
                if path.name in _MANIFESTS:
                    manifests.append(RepositoryManifest(
                        relative_text, _ecosystem(path.name), root.name, (), digest,
                    ))
            if len(files) >= self._maximum_files:
                break
        return files, contexts, manifests, total, truncated


def _role(path):
    text = path.as_posix().lower()
    if path.name in _MANIFESTS:
        return RepositoryFileRole.MANIFEST
    if text.startswith("tests/") or "/test" in text:
        return RepositoryFileRole.TEST
    if path.suffix.lower() in {".md", ".rst"}:
        return RepositoryFileRole.DOCUMENTATION
    return RepositoryFileRole.SOURCE


def _language(path):
    return {".py": "python", ".ts": "typescript", ".js": "javascript", ".rs": "rust", ".go": "go", ".java": "java", ".cs": "csharp"}.get(path.suffix.lower())


def _ecosystem(name):
    return {"pyproject.toml": "python", "package.json": "node", "Cargo.toml": "rust", "go.mod": "go", "pom.xml": "java", "build.gradle": "java"}[name]


def _text(content, maximum):
    if len(content) > maximum:
        return None
    try:
        value = content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return value if value.strip() else None


def _revision(files, head, diff):
    payload = "\n".join(f"{item.path}:{item.content_sha256}" for item in files)
    return "sha256:" + hashlib.sha256(f"{head}:{diff}:{payload}".encode()).hexdigest()


def _status_path(value):
    path = value[3:] if len(value) > 3 else value
    return path.rsplit(" -> ", 1)[-1]


def _git_state(observation):
    if observation is None:
        return RepositoryGitState("unversioned", "unversioned", (), (), False)
    return RepositoryGitState(
        observation.head_ref, observation.head_object_id or "unborn",
        observation.remote_names,
        tuple(_status_path(item) for item in observation.status_porcelain),
        False,
    )
